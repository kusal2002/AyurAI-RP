"""Provisional research pathway: planning, isolation, idempotent writes, verification.

Synthetic TEI source and synthetic drafts only; no live database.
"""

import json
import re
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.knowledge_ingestion.cli import main as ingest_main
from app.knowledge_provisional.cli import main as prov_main
from app.knowledge_provisional.plan import plan_dataset, provisional_claim_id
from app.knowledge_provisional.writer import verify_plan, write_claim, write_reference
from app.models.c1_input import Component2ReasoningRequest
from app.models.c2_output import Decision, SufficiencyStatus
from app.reasoning.pipeline import run_component2_reasoning
from c2_test_support import FakeGraph, make_retrieval_service
from ingestion_test_support import SYNTHETIC_TEI_BODY, make_tei


SIDECAR = {
    "source_id": "syn", "title": "Synthetic Samhita", "edition": "test",
    "source_language": "sa", "evidence_category": "traditional_text",
    "usage_notes": "Licence: CC BY-SA (test fixture)",
}

CONCEPTS = [
    {"type": "Symptom", "id": "S-PALLOR", "name": "pallor", "aliases": ["paleness"]},
    {"type": "Roga", "id": "R-PANDU", "name": "Pandu", "aliases": []},
    {"type": "TherapeuticPrinciple", "id": "TP-SYN", "name": "Synthetic principle", "aliases": []},
    {"type": "Herb", "id": "H-PUNARNAVA", "name": "Punarnavā", "aliases": [],
     "botanical_name_as_stated": "Boerhavia diffusa", "botanical_name_source": "syn"},
]


def _claim(key, s, p, o, quote="Pallor is a symptom of pandu.", element="Syn.6.16.2", **extra):
    item = {"key": key, "category": "test", "subject": s, "predicate": p, "object": o,
            "statement": f"{s} {p} {o} (synthetic)",
            "evidence": [{"source_id": "syn", "element_id": element, "quote": quote}],
            "uncertainty": ["synthetic"]}
    item.update(extra)
    return item


BASE_CLAIMS = [
    _claim("pallor-pandu", "S-PALLOR", "INDICATES", "R-PANDU"),
    _claim("pandu-tp", "R-PANDU", "SUGGESTS_PRINCIPLE", "TP-SYN", quote="pāṇḍuroge lakṣaṇāni vakṣyāmi/", element="Syn.6.16.1"),
    _claim("tp-herb", "TP-SYN", "USES_HERB", "H-PUNARNAVA", quote="triphalā punarnavā ca", element="Syn.6.16.3",
           qualified_by_reference=["ref-1"]),
]


def _dataset(tmp_path, claims=None, refs=None, **overrides):
    data = {
        "dataset_id": "syn-prov", "dataset_version": "1", "drafted_on": "2026-10-20",
        "extraction_method": "ai_assisted_draft", "review_status": "pending_practitioner_review",
        "concepts": CONCEPTS, "claims": claims if claims is not None else BASE_CLAIMS,
        "reference_evidence": refs if refs is not None else [
            {"key": "ref-1", "category": "modern_diet", "topics": ["t"], "source_id": "syn",
             "quote": "tvak pāṇḍutā ca dṛśyate", "uncertainty": []},
        ],
        "known_gaps": ["synthetic gap"],
    }
    data.update(overrides)
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def extracted(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "extracted"
    raw.mkdir()
    make_tei(raw / "syn.xml", SYNTHETIC_TEI_BODY)
    (raw / "syn.xml.meta.json").write_text(json.dumps(SIDECAR), encoding="utf-8")
    assert ingest_main(["manifest", str(raw), "--out", str(out / "manifest.json"), "--extract-dir", str(out)]) == 0
    assert ingest_main(["chunk", str(out)]) == 0
    return out


# --- planning ------------------------------------------------------------------

def test_plan_locates_quotes_and_keeps_provenance(tmp_path, extracted):
    plan = plan_dataset(_dataset(tmp_path), extracted)
    assert plan.rejected == [] and len(plan.claims) == 3
    for claim in plan.claims.values():
        assert claim.properties["verification_status"] == "unverified"
        assert claim.properties["knowledge_status"] == "provisional"
        assert claim.properties["extraction_method"] == "ai_assisted_draft"
        for evidence_id in claim.evidence_ids:
            props = plan.evidence[evidence_id].properties
            assert props["source_id"] == "syn" and props["chunk_id"].startswith("syn#chk-")
            assert props["citation"].startswith("Syn.6.16.")
            assert props["evidence_type"] == "classical"
            assert props["licence_note"].startswith("Licence:")
    herb = plan.claims[provisional_claim_id("TP-SYN", "USES_HERB", "H-PUNARNAVA")]
    assert herb.qualifier_ids and plan.evidence[herb.qualifier_ids[0]].role == "modern_reference"
    assert plan.concepts["H-PUNARNAVA"]["properties"]["botanical_name_verified"] is False


def test_plan_ids_are_deterministic(tmp_path, extracted):
    first, second = plan_dataset(_dataset(tmp_path), extracted), plan_dataset(_dataset(tmp_path), extracted)
    assert list(first.claims) == list(second.claims)
    assert list(first.evidence) == list(second.evidence)


@pytest.mark.parametrize("claim, reason", [
    (_claim("bad-quote", "S-PALLOR", "INDICATES", "R-PANDU", quote="this text is not in the source"), "quote not found"),
    (_claim("wrong-verse", "S-PALLOR", "INDICATES", "R-PANDU", element="Syn.6.16.1"), "quote not found in passage"),
    (_claim("undeclared", "S-FEVER", "INDICATES", "R-PANDU"), "undeclared concept"),
    (_claim("ontology", "H-PUNARNAVA", "INDICATES", "R-PANDU"), "ontology"),
])
def test_unsupported_claims_are_rejected(tmp_path, extracted, claim, reason):
    plan = plan_dataset(_dataset(tmp_path, claims=[claim]), extracted)
    assert plan.claims == {}
    assert any(reason in r["reason"] for r in plan.rejected), plan.rejected


def test_translation_only_claim_is_rejected(tmp_path, extracted):
    claim = _claim("translation-only", "S-PALLOR", "INDICATES", "R-PANDU")
    claim["evidence"][0]["role"] = "translation"
    plan = plan_dataset(_dataset(tmp_path, claims=[claim]), extracted)
    assert plan.claims == {} and "no located primary-source quote" in plan.rejected[-1]["reason"]


def test_duplicates_are_reported_not_merged(tmp_path, extracted):
    claims = [BASE_CLAIMS[0], dict(BASE_CLAIMS[0]), dict(BASE_CLAIMS[0], key="other-key")]
    plan = plan_dataset(_dataset(tmp_path, claims=claims), extracted)
    assert len(plan.claims) == 1
    assert {d["reason"].split(" ")[0] for d in plan.duplicates} == {"duplicate", "same"}


def test_source_without_curated_metadata_is_rejected(tmp_path, extracted):
    for meta in extracted.glob("*.extraction.json"):
        data = json.loads(meta.read_text(encoding="utf-8"))
        data["source"]["metadata"]["usage_notes"] = None
        meta.write_text(json.dumps(data), encoding="utf-8")
    plan = plan_dataset(_dataset(tmp_path), extracted)
    assert plan.claims == {} and any("licence" in r["reason"] for r in plan.rejected)


def test_only_ai_assisted_drafts_are_accepted(tmp_path, extracted):
    with pytest.raises(ValueError):
        plan_dataset(_dataset(tmp_path, extraction_method="practitioner_approved"), extracted)


# --- writes ------------------------------------------------------------------------

class RecordingTx:
    def __init__(self):
        self.queries = []

    def run(self, query, **params):
        self.queries.append((query, params))
        result = MagicMock()
        result.__iter__ = lambda self_: iter([{"ok": 1}])
        result.consume.return_value.counters = MagicMock(**{k: 0 for k in (
            "nodes_created", "relationships_created", "properties_set", "labels_added",
            "labels_removed", "nodes_deleted", "relationships_deleted")})
        return result


def test_writes_are_additive_merges_isolated_from_approved_pathway(tmp_path, extracted):
    plan = plan_dataset(_dataset(tmp_path), extracted)
    tx = RecordingTx()
    for evidence_id, ev in plan.evidence.items():
        if ev.role == "modern_reference":
            write_reference(tx, evidence_id, plan, "batch-t", "2026-10-20T00:00:00Z")
    for claim_id in plan.claims:
        write_claim(tx, claim_id, plan, "batch-t", "2026-10-20T00:00:00Z")
    text = "\n".join(q for q, _ in tx.queries)
    for forbidden in ("DELETE", "DETACH", "REMOVE ", "DROP", "CREATE ("):
        assert forbidden not in text
    assert not re.search(r":(Claim|Evidence)\b", text), "approved labels must never be written"
    assert not re.search(r"\[:(SUBJECT_OF|OBJECT_OF|SUPPORTS|CONTRADICTS)\]", text)
    assert "MERGE (claim:ProvisionalClaim {claim_id: $claim_id})" in text
    statuses = {params["properties"]["verification_status"] for q, params in tx.queries
                if "MERGE (claim:ProvisionalClaim" in q and "properties" in params}
    assert statuses == {"unverified"}


def test_cli_apply_refuses_without_confirmation(tmp_path, extracted, monkeypatch, capsys):
    import app.db.neo4j as neo
    monkeypatch.setattr(neo, "get_neo4j_driver", MagicMock(return_value=MagicMock()))
    assert prov_main(["apply", str(_dataset(tmp_path)), "--extracted", str(extracted)]) == 2
    assert "Refusing to write" in capsys.readouterr().out


# --- verification -------------------------------------------------------------------

def _fake_graph_reader(plan, tamper=None, leaked=0):
    claims = [{
        "id": c.claim_id, "status": "unverified", "ks": "provisional",
        "sid": c.triple[0], "p": c.triple[1], "oid": c.triple[2], "statement": c.properties["statement"],
        "subjects": [{}], "objects": [{}], "evidence": list(c.evidence_ids), "qualifiers": list(c.qualifier_ids),
    } for c in plan.claims.values()]
    evidence = [{
        "id": e.evidence_id, "text": e.properties["text"], "source_id": e.source_id, "role": e.role,
        "chunk_id": e.chunk_id, "chunk_source": e.source_id,
        "sha": plan.sources[e.source_id]["content_sha256"], "start": e.span[0], "end": e.span[1],
    } for e in plan.evidence.values()]
    if tamper:
        evidence[0]["text"] = "changed"

    def router(cypher):
        if "ProvisionalClaim {dataset_id" in cypher:
            return claims
        if "ProvisionalEvidence {dataset_id" in cypher:
            return evidence
        if "n:Claim OR n:Evidence" in cypher:
            return [{"c": leaked}]
        return [{"c": 0}]

    return router


def test_verification_detects_mismatches(tmp_path, extracted, monkeypatch):
    import app.knowledge_provisional.writer as writer
    plan = plan_dataset(_dataset(tmp_path), extracted)
    for tamper, leaked, expected in ((None, 0, "verified"), (True, 0, "mismatch"), (None, 2, "mismatch")):
        router = _fake_graph_reader(plan, tamper=tamper, leaked=leaked)
        monkeypatch.setattr(writer, "_read", lambda driver, cypher, **params: router(cypher))
        assert verify_plan(plan, MagicMock())["status"] == expected


# --- reasoning: approved isolation and research labelling -------------------------------

class PlanGraph:
    """ResearchGraphAccess stand-in built from a plan (approved + provisional)."""

    knowledge_scope = "approved_and_provisional"

    def __init__(self, plan):
        self.plan = plan

    def _concept(self, cid):
        c = self.plan.concepts[cid]
        return {c["id_property"]: cid, **c["properties"]}

    def get_symptom(self, symptom_id, driver=None):
        c = self.plan.concepts.get(symptom_id)
        return self._concept(symptom_id) if c and c["label"] == "Symptom" else None

    def get_concepts(self, ids, driver=None):
        return {cid: {"labels": [self.plan.concepts[cid]["label"]], "properties": self._concept(cid)}
                for cid in ids if cid in self.plan.concepts}

    def _evidence(self, ids):
        return [dict(self.plan.evidence[e].properties, evidence_id=e) for e in ids]

    def get_claims_for_concept(self, cid, driver=None):
        out = []
        for c in self.plan.claims.values():
            if c.triple[0] == cid:
                out.append({"claim": dict(c.properties), "role": "subject"})
            if c.triple[2] == cid:
                out.append({"claim": dict(c.properties), "role": "object"})
        return out

    def get_connected_knowledge(self, cid, driver=None):
        return [{"claim": dict(c.properties), "supporting_evidence": self._evidence(c.evidence_ids),
                 "contradicting_evidence": [], "qualifying_evidence": self._evidence(c.qualifier_ids)}
                for c in self.plan.claims.values() if cid in (c.triple[0], c.triple[2])]

    def get_evidence_for_claim(self, claim_id, driver=None):
        c = self.plan.claims.get(claim_id)
        return None if c is None else {"claim": dict(c.properties), "evidence": [
            {"evidence": e, "relationship": "SUPPORTS"} for e in self._evidence(c.evidence_ids)]}

    def list_evidence(self, driver=None):
        return self._evidence(list(self.plan.evidence))


REQUEST = Component2ReasoningRequest(request_id="req-prov", risk_tier="moderate",
                                     calibrated_confidence=0.9, symptom_ids=["S-PALLOR"])


def test_approved_scope_never_sees_provisional_claims(tmp_path, extracted):
    # The approved repository has the concept but no approved claims.
    approved = FakeGraph()
    approved.add_concept("Symptom", "S-PALLOR", "pallor")
    with approved.patched():
        output = run_component2_reasoning(REQUEST, retrieval_service=make_retrieval_service(approved))
    assert output.knowledge_scope == "approved"
    assert output.candidates == [] and output.decision == Decision.ABSTAIN
    assert "provisional_unverified_knowledge_used" not in output.uncertainty_flags


def test_research_scope_labels_everything_and_never_recommends(tmp_path, extracted):
    plan = plan_dataset(_dataset(tmp_path), extracted)
    graph = PlanGraph(plan)
    service = make_retrieval_service(graph)
    output = run_component2_reasoning(REQUEST, retrieval_service=service, graph=graph)

    assert output.knowledge_scope == "approved_and_provisional"
    [herb] = output.candidates
    assert herb.candidate_id == "H-PUNARNAVA"
    # One synthetic source: too few independent sources as well as unverified;
    # either way a provisional path is never sufficient.
    assert herb.sufficiency.status != SufficiencyStatus.SUFFICIENT_FOR_REVIEW
    assert herb.disposition.value == "withheld_pending_review"
    assert "provisional_unverified_claim" in herb.sufficiency.uncertainty_flags
    steps = [s for p in herb.paths for s in p.claims]
    assert steps and all(s.knowledge_status == "provisional" for s in steps)
    refs = [r for s in steps for r in s.supporting_evidence]
    assert refs and all(r.knowledge_status == "provisional" and r.source_id == "syn" for r in refs)
    herb_step = next(s for s in steps if s.predicate == "USES_HERB")
    assert herb_step.qualifying_evidence and herb_step.qualifying_evidence[0].evidence_role == "modern_reference"
    assert herb_step.uncertainty_notes == ["synthetic"]
    assert output.decision in (Decision.CAUTION, Decision.ABSTAIN)
    assert "provisional_unverified_knowledge_used" in output.uncertainty_flags
    assert "knowledge:provisional_records_used" in output.decision_reasons
    assert any("Research scope" in note for note in output.limitations)
    assert output.medical_conclusion is None


# --- API -------------------------------------------------------------------------

def test_api_scope_parameter(tmp_path, extracted, monkeypatch):
    from app.api.c2 import get_driver, get_research_service
    from app.main import app
    from app.retrieval.service import get_retrieval_service
    import app.db.research_repository as research

    plan = plan_dataset(_dataset(tmp_path), extracted)
    graph = PlanGraph(plan)
    monkeypatch.setattr(research, "ResearchGraphAccess", lambda driver: graph)
    approved = FakeGraph()
    approved.add_concept("Symptom", "S-PALLOR", "pallor")
    app.dependency_overrides[get_driver] = lambda: MagicMock()
    app.dependency_overrides[get_retrieval_service] = lambda: make_retrieval_service(approved)
    app.dependency_overrides[get_research_service] = lambda: make_retrieval_service(graph)
    body = {"request_id": "req-api-prov", "risk_tier": "moderate", "calibrated_confidence": 0.9,
            "symptom_ids": ["S-PALLOR"]}
    try:
        client = TestClient(app)
        with approved.patched():
            default = client.post("/api/v1/c2/reasoning", json=body).json()
        assert default["knowledge_scope"] == "approved" and default["candidates"] == []
        research_out = client.post("/api/v1/c2/reasoning?knowledge_scope=approved_and_provisional", json=body).json()
        assert research_out["knowledge_scope"] == "approved_and_provisional"
        assert research_out["candidates"][0]["paths"][0]["claims"][0]["knowledge_status"] == "provisional"
        assert client.post("/api/v1/c2/reasoning?knowledge_scope=everything", json=body).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_research_knowledge_endpoint_reports_outage(monkeypatch):
    from neo4j.exceptions import ServiceUnavailable
    from app.api.c2 import get_driver
    from app.main import app
    import app.db.research_repository as research

    monkeypatch.setattr(research, "list_provisional_knowledge", MagicMock(side_effect=ServiceUnavailable("down")))
    app.dependency_overrides[get_driver] = lambda: MagicMock()
    try:
        response = TestClient(app).get("/api/v1/c2/research/knowledge")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
