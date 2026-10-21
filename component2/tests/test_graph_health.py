"""Health/readiness endpoints and read-only graph validation (no live DB)."""

import re

import pytest
from fastapi.testclient import TestClient
from neo4j import READ_ACCESS
from neo4j.exceptions import AuthError, ClientError, ServiceUnavailable

import app.api.neo4j_health as health
from app.db import neo4j as neo4j_module
from app.db.graph_validation import CORE_CONSTRAINTS, validate_graph
from app.main import app


class FakeRecord(dict):
    def data(self):
        return dict(self)

    def __getitem__(self, key):
        return dict.__getitem__(self, key)


class FakeResult(list):
    def single(self):
        return self[0] if self else None


class FakeTx:
    def __init__(self, router, log):
        self.router = router
        self.log = log

    def run(self, cypher, **params):
        self.log.append(cypher)
        return FakeResult(FakeRecord(row) for row in self.router(cypher, params))


class FakeSession:
    def __init__(self, driver, config):
        self.driver = driver
        driver.session_configs.append(config)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute_read(self, work):
        if self.driver.error:
            raise self.driver.error
        return work(FakeTx(self.driver.router, self.driver.queries))

    def execute_write(self, work):  # pragma: no cover - must never be used
        raise AssertionError("validation attempted a write transaction")

    def run(self, *args, **kwargs):  # pragma: no cover - must never be used
        raise AssertionError("validation used an auto-commit query")


class FakeDriver:
    def __init__(self, router=None, error=None):
        self.router = router or (lambda cypher, params: [])
        self.error = error
        self.queries: list[str] = []
        self.session_configs: list[dict] = []

    def session(self, **config):
        return FakeSession(self, config)


# --- connectivity classification -------------------------------------------

def _ping_router(cypher, params):
    return [{"ok": 1}]


@pytest.mark.parametrize(
    "error, status",
    [
        (None, "healthy"),
        (AuthError("bad credentials"), "auth_failed"),
        (ServiceUnavailable("no route"), "unreachable"),
        (OSError("dns"), "unreachable"),
        (ClientError("syntax"), "query_failed"),
    ],
)
def test_check_neo4j_classifies_failures_without_secrets(monkeypatch, error, status):
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://secret-host.example:7687")
    driver = FakeDriver(_ping_router, error=error)
    result = neo4j_module.check_neo4j(driver)
    assert result["status"] == status
    assert result["encrypted"] is True
    assert "secret-host" not in str(result) and "bad credentials" not in str(result)
    assert driver.session_configs[0]["default_access_mode"] == READ_ACCESS


def test_check_neo4j_reports_missing_configuration(monkeypatch):
    for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    neo4j_module.get_neo4j_driver.cache_clear()
    try:
        assert neo4j_module.check_neo4j()["status"] == "not_configured"
    finally:
        neo4j_module.get_neo4j_driver.cache_clear()


@pytest.mark.parametrize(
    "uri, allowed",
    [
        ("neo4j+s://x.databases.neo4j.io", True),
        ("bolt+s://db.example.org:7687", True),
        ("neo4j://localhost:7687", True),
        ("bolt://127.0.0.1:7687", True),
        ("neo4j://db.example.org:7687", False),
        ("bolt://10.0.0.5:7687", False),
    ],
)
def test_remote_database_requires_encrypted_scheme(uri, allowed):
    if allowed:
        neo4j_module._check_uri(uri)
    else:
        with pytest.raises(RuntimeError) as info:
            neo4j_module._check_uri(uri)
        assert "example" not in str(info.value) and "10.0.0.5" not in str(info.value)


def test_driver_gets_timeouts(monkeypatch):
    monkeypatch.setenv("C2_NEO4J_CONNECTION_TIMEOUT", "3")
    settings = neo4j_module.connection_settings()
    assert settings["connection_timeout"] == 3.0
    assert settings["connection_acquisition_timeout"] > 0
    monkeypatch.setenv("C2_NEO4J_CONNECTION_TIMEOUT", "0")
    with pytest.raises(RuntimeError):
        neo4j_module.connection_settings()


# --- endpoints ---------------------------------------------------------------

def test_neo4j_health_unavailable_is_explicit_503(monkeypatch):
    monkeypatch.setattr(health, "check_neo4j", lambda: {
        "status": "unreachable", "detail": "database server could not be reached",
        "encrypted": True,
    })
    response = TestClient(app).get("/health/neo4j")
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["connected"] is False and detail["reason"] == "unreachable"


def test_readiness_when_database_down_reports_nothing_as_available(monkeypatch, tmp_path):
    monkeypatch.setattr(health, "check_neo4j", lambda: {
        "status": "auth_failed", "detail": "authentication was rejected", "encrypted": True,
    })
    monkeypatch.setenv("C2_CORPUS_MANIFEST", str(tmp_path / "absent.json"))
    body = TestClient(app).get("/health/readiness").json()
    assert body["ready_for_reasoning"] is False
    assert body["knowledge_available"] is False
    components = body["components"]
    assert components["database_connectivity"]["status"] == "auth_failed"
    assert components["graph_schema"]["status"] == "unknown"
    assert components["knowledge_graph_content"]["status"] == "unknown"
    assert components["local_corpus_ingestion"]["status"] == "not_found"
    assert components["retrieval_service"]["status"] in {"not_initialised", "ready", "unavailable"}
    assert "embedding_model" in components and "component_integration" in components


def test_readiness_distinguishes_connected_from_populated(monkeypatch, tmp_path):
    monkeypatch.setattr(health, "check_neo4j", lambda: {
        "status": "healthy", "detail": "ok", "encrypted": True,
    })
    monkeypatch.setattr(health, "_graph_summary", lambda: {
        "graph_schema": {"status": "core_constraints_present", "missing_core_constraints": [],
                         "stage_e_applied": False},
        "knowledge_graph_content": {"status": "empty", "node_counts": {"Claim": 0}},
    })
    monkeypatch.setenv("C2_CORPUS_MANIFEST", str(tmp_path / "absent.json"))
    body = TestClient(app).get("/health/readiness").json()
    assert body["ready_for_reasoning"] is True
    assert body["knowledge_available"] is False
    assert any("does not mean the corpus is complete" in note for note in body["notes"])


def test_graph_validation_endpoint_503_when_down(monkeypatch):
    monkeypatch.setattr(health, "check_neo4j", lambda: {
        "status": "unreachable", "detail": "x", "encrypted": None,
    })
    assert TestClient(app).get("/health/graph-validation").status_code == 503


# --- validation --------------------------------------------------------------

def _graph_router(counts=None, constraints=CORE_CONSTRAINTS, findings=None,
                  rel_types=("SUBJECT_OF", "OBJECT_OF", "SUPPORTS")):
    counts = counts if counts is not None else {"Claim": 2, "Evidence": 3, "Symptom": 1, "Roga": 1}
    findings = findings or {}

    def router(cypher, params):
        if "dbms.components" in cypher:
            return [{"name": "Neo4j Kernel", "versions": ["5.27-aura"], "edition": "enterprise"}]
        if "db.labels" in cypher:
            return [{"label": label} for label in counts]
        if "db.relationshipTypes" in cypher:
            return [{"relationshipType": t} for t in rel_types]
        if "SHOW CONSTRAINTS" in cypher:
            return [{"name": name} for name in constraints]
        match = re.match(r"MATCH \(n:`(\w+)`\) RETURN count\(n\)", cypher)
        if match:
            return [{"c": counts[match.group(1)]}]
        if re.match(r"MATCH \(\)-\[x:`\w+`\]->\(\) RETURN count", cypher):
            return [{"c": 4}]
        for needle, (total, sample) in findings.items():
            if needle in cypher:
                return [{"total": total, "sample": sample}]
        return [{"total": 0, "sample": []}]

    return router


def test_clean_graph_is_valid_and_reads_only():
    driver = FakeDriver(_graph_router())
    report = validate_graph(driver)
    assert report.status in {"valid", "valid_with_warnings"}
    assert report.errors == 0
    assert driver.session_configs[0]["default_access_mode"] == READ_ACCESS
    writes = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP)\b")
    assert not [q for q in driver.queries if writes.search(q.replace("SHOW CONSTRAINTS", ""))]
    assert any(f.check == "stage_e_schema_not_applied" for f in report.findings)


def test_validation_reports_integrity_problems_with_ids():
    driver = FakeDriver(_graph_router(
        findings={
            "NOT c.predicate IN $predicates": (1, ["CL-BAD"]),
            "OPTIONAL MATCH (s)-[:SUBJECT_OF]->(c)": (2, ["CL-1", "CL-2"]),
            "NOT (e)-[:SUPPORTS|CONTRADICTS]->(:Claim)": (1, ["EV-ORPHAN"]),
        },
        rel_types=("SUBJECT_OF", "INVENTED_LINK"),
        constraints=CORE_CONSTRAINTS - {"claim_id_unique"},
    ))
    report = validate_graph(driver)
    by_check = {f.check: f for f in report.findings}
    assert report.status == "invalid"
    assert by_check["claim_unknown_predicate"].sample_ids == ["CL-BAD"]
    assert by_check["claim_subject_link"].count == 2
    assert by_check["orphaned_evidence"].severity == "warning"
    assert by_check["unknown_relationship_types"].sample_ids == ["INVENTED_LINK"]
    assert by_check["missing_core_constraints"].sample_ids == ["claim_id_unique"]
    # Without a uniqueness constraint, duplicates are checked explicitly.
    assert any("WITH n.`claim_id` AS key" in q for q in driver.queries)


def test_empty_graph_says_reasoning_will_abstain():
    report = validate_graph(FakeDriver(_graph_router(counts={"Claim": 0})))
    assert any(f.check == "no_approved_claims" for f in report.findings)


def test_validation_propagates_outage():
    with pytest.raises(ServiceUnavailable):
        validate_graph(FakeDriver(error=ServiceUnavailable("down")))
