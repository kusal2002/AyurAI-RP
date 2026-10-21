"""End-to-end: registered source -> passages -> graph -> API response.

Every stage runs the real code (registry acquisition, TEI extraction,
chunking, candidate extraction, human review, promotion planning and the
promotion write function, the reasoning API) on a synthetic TEI file.
Only the network and Neo4j are replaced: downloads come from an in-memory
opener, the promotion transaction runs against the recording fake driver
used by the Stage E tests, and reasoning reads an in-memory FakeGraph
that is built from exactly what promotion would write. No live database
is touched.
"""

import csv
import hashlib
import io
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from app.api.c2 import get_driver
from app.db.source_repository import plan_modelled_promotions, plan_promotions, write_plan
from app.knowledge_candidates.modelled import ModelledStore
from app.knowledge_ingestion.cli import _load_promotion_inputs, main
from app.knowledge_ingestion.registry import REGISTRY_COLUMNS
from app.knowledge_ingestion.service import (
    iter_extraction_summaries,
    load_extraction_output,
)
from app.main import app
from app.retrieval.service import get_retrieval_service
from c2_test_support import FakeGraph, KeywordEncoder, make_retrieval_service
from ingestion_test_support import SYNTHETIC_TEI_BODY, make_tei
from test_stage_e_promotion import FakeDriver as RecordingDriver


TITLE = "Synthetic Samhita (test edition)"
URL = "https://example.org/synthetic-samhita.xml"


class _Response(io.BytesIO):
    status = 200


def _registry(tmp_path, payload: bytes, **overrides):
    row = {column: "" for column in REGISTRY_COLUMNS}
    row.update(
        registry_id="T-E2E", status="candidate", decision="include",
        source_id="syn-samhita", title=TITLE, edition="test",
        source_language="sa", evidence_category="traditional_text",
        licence="CC BY-SA 3.0 (test)", licence_evidence="fixture",
        download_url=URL, checksum_type="sha256",
        checksum=hashlib.sha256(payload).hexdigest(),
        local_relative_path="classical_open/syn.xml",
    )
    row.update(overrides)
    path = tmp_path / "registry.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    return path


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Run acquisition through candidate extraction with the real CLI."""
    payload = make_tei(tmp_path / "upstream.xml", SYNTHETIC_TEI_BODY).read_bytes()
    raw, extracted = tmp_path / "raw", tmp_path / "extracted"
    candidates = extracted / "candidates"
    registry = _registry(tmp_path, payload)

    from app.knowledge_ingestion import registry as registry_module
    monkeypatch.setattr(registry_module, "_default_opener",
                        lambda request, timeout: _Response(payload))
    monkeypatch.setattr(registry_module.time, "sleep", lambda seconds: None)

    assert main(["acquire", str(registry), "--raw", str(raw), "--apply"]) == 0
    assert main(["manifest", str(raw), "--out", str(extracted / "manifest.json"),
                 "--extract-dir", str(extracted)]) == 0
    assert main(["chunk", str(extracted)]) == 0
    assert main(["validate", str(extracted)]) == 0
    assert main(["candidates-extract", str(extracted), "--out", str(candidates)]) == 0
    return {"raw": raw, "extracted": extracted, "candidates": candidates}


def _symptom_candidate(candidates_dir):
    rows = [json.loads(line) for line in (candidates_dir / "candidates.jsonl").open(encoding="utf-8")]
    matches = [r for r in rows if r["predicate"] == "HAS_SYMPTOM"
               and r["subject"]["concept_id"] == "R-PANDU"
               and r["object"]["concept_id"] == "S-PALLOR"]
    assert len(matches) == 1, [(r["subject"]["concept_id"], r["predicate"], r["object"]["concept_id"]) for r in rows]
    return matches[0]


def _approve(candidates_dir, claim_id):
    assert main(["review", str(candidates_dir), claim_id, "--status", "approved",
                 "--reviewer", "Test Practitioner", "--role", "practitioner",
                 "--note", "Checked against the synthetic fixture text."]) == 0


def _plan(corpus):
    """Candidate and reviewer-modelled plans, as the promote command builds them."""
    candidates, conflicts, sources, chunks, log = _load_promotion_inputs(
        corpus["candidates"], corpus["extracted"])
    report = plan_promotions(candidates.values(), conflicts, sources, chunks, review_log=log)
    store = ModelledStore(corpus["candidates"])
    modelled = plan_modelled_promotions(store.load().values(), sources, chunks,
                                        modelled_log=store.load_log())
    report.plans.extend(modelled.plans)
    report.skipped.extend(modelled.skipped)
    return report


def _model(corpus, chunk_id, quote, subject, predicate, obj):
    return main([
        "model-claim", str(corpus["candidates"]), "--extracted", str(corpus["extracted"]),
        "--chunk-id", chunk_id, "--quote", quote, "--subject", subject,
        "--predicate", predicate, "--object", obj,
        "--statement", f"{subject} {predicate} {obj} (synthetic fixture)",
        "--reviewer", "Test Practitioner", "--role", "practitioner",
        "--note", "Synthetic fixture verse; modelled for the test.",
    ])


def _graph_from_plans(plans) -> FakeGraph:
    """What reasoning would read after promotion: the planned nodes only."""
    graph = FakeGraph()
    for plan in plans:
        for concept in plan.concepts:
            graph.add_concept(concept.label, concept.concept_id, concept.name)
        evidence = dict(plan.evidence_properties)
        graph.evidence[evidence["evidence_id"]] = evidence
        props = plan.claim_properties
        graph.add_claim(
            plan.claim_id, *plan.triple, status=props["verification_status"],
            statement=props.get("statement"), supports=[evidence["evidence_id"]],
        )
    return graph


@pytest.fixture
def api():
    stacks = []

    def make(graph, encoder=None):
        app.dependency_overrides[get_driver] = lambda: MagicMock()
        service = make_retrieval_service(graph, encoder=encoder or KeywordEncoder())
        app.dependency_overrides[get_retrieval_service] = lambda: service
        stack = graph.patched()
        stack.__enter__()
        stacks.append(stack)
        return TestClient(app)

    yield make
    for stack in stacks:
        stack.__exit__(None, None, None)
    app.dependency_overrides.clear()


REQUEST = {"request_id": "req-e2e-1", "risk_tier": "moderate",
           "calibrated_confidence": 0.6, "symptom_ids": ["S-PALLOR"]}


def test_source_passage_keeps_identity_provenance_and_language(corpus):
    sidecar = json.loads((corpus["raw"] / "classical_open" / "syn.xml.meta.json").read_text(encoding="utf-8"))
    assert sidecar["source_id"] == "syn-samhita" and sidecar["evidence_category"] == "traditional_text"
    [summary] = iter_extraction_summaries(corpus["extracted"])
    record, passages = load_extraction_output(summary)
    assert record.source_id == "syn-samhita" and record.source_id_origin == "metadata"
    assert record.metadata.source_language == "sa"
    assert "Licence: CC BY-SA 3.0 (test)" in record.metadata.usage_notes
    verse = next(p for p in passages if p.location.element_id == "Syn.6.16.2")
    assert verse.location.section_heading == "pāṇḍurogacikitsitam"

    candidate = _symptom_candidate(corpus["candidates"])
    passage = candidate["passage"]
    assert passage["source_id"] == "syn-samhita"
    assert passage["chunk_id"].startswith("syn-samhita#chk-")
    assert "Syn.6.16.2" in passage["citation_refs"]
    assert passage["declared_source_language"] == "sa"


def test_unreviewed_candidates_never_reach_the_graph(corpus):
    report = _plan(corpus)
    assert report.plans == []
    assert all("not approved" in reason for _, reason in report.skipped)


def test_promoted_evidence_is_retrieved_and_traceable_through_api(corpus, api):
    candidate = _symptom_candidate(corpus["candidates"])
    _approve(corpus["candidates"], candidate["claim_id"])
    report = _plan(corpus)
    [plan] = report.plans
    assert plan.triple == ("S-PALLOR", "INDICATES", "R-PANDU")
    evidence = plan.evidence_properties
    assert evidence["source_id"] == "syn-samhita"
    assert evidence["chunk_id"] == candidate["passage"]["chunk_id"]
    assert evidence["citation"].startswith("chunk covers Syn.6.16.1")
    assert evidence["source_name"].startswith(TITLE)
    assert plan.claim_properties["verification_status"] == "practitioner_verified"

    # The single write transaction runs (against the recording fake) with
    # idempotent MERGEs only.
    driver = RecordingDriver()
    with driver.session() as session:
        session.execute_write(lambda tx: write_plan(tx, plan, "batch-test", "2026-10-19T00:00:00Z"))
    assert driver.committed and all("DELETE" not in q for q, _ in driver.committed)
    assert any("MERGE" in q for q, _ in driver.committed)

    client = api(_graph_from_plans(report.plans))
    body = client.post("/api/v1/c2/reasoning", json=REQUEST).json()

    [mapping] = body["symptom_mappings"]
    assert mapping["found"] and mapping["indicates_claim_ids"] == [plan.claim_id]
    [pandu] = body["interpretation"]
    assert pandu["concept_id"] == "R-PANDU"
    assert pandu["supporting_evidence_ids"] == [evidence["evidence_id"]]
    # An interpretation alone yields no recommendation: explicit abstention.
    assert body["candidates"] == []
    assert body["sufficiency_status"] == "insufficient_evidence"
    assert body["abstention"]["abstain"] is True
    assert "no_valid_candidate_path_found" in body["abstention"]["reasons"]
    # Open retrieval returns the promoted passage with its provenance.
    hit = next(h for h in body["retrieved_evidence"] if h["evidence_id"] == evidence["evidence_id"])
    assert hit["source_id"] == "syn-samhita"
    assert hit["source_chunk_id"] == evidence["chunk_id"]
    assert hit["linked_to_traversed_claim"] is True


def test_candidate_explanation_cites_only_retrieved_evidence(corpus, api):
    """Treatment claims are authored by a reviewer with model-claim (the
    ontology routes treatment through a principle) from exact quotes, then
    promoted alongside the extracted symptom claim."""
    candidate = _symptom_candidate(corpus["candidates"])
    _approve(corpus["candidates"], candidate["claim_id"])
    chunk_id = candidate["passage"]["chunk_id"]
    assert _model(corpus, chunk_id, "pāṇḍuroge lakṣaṇāni vakṣyāmi/",
                  "Roga:R-PANDU:Pandu", "SUGGESTS_PRINCIPLE",
                  "TherapeuticPrinciple:TP-SYN:Synthetic principle") == 0
    assert _model(corpus, chunk_id, "triphalā\npunarnavā ca",
                  "TherapeuticPrinciple:TP-SYN:Synthetic principle", "USES_HERB",
                  "Herb:H-PUNARNAVA:Punarnava") == 0
    # An invented quote is refused rather than stored.
    assert _model(corpus, chunk_id, "punarnava cures anaemia in all cases",
                  "TherapeuticPrinciple:TP-SYN:Synthetic principle", "USES_HERB",
                  "Herb:H-PUNARNAVA:Punarnava") == 1

    report = _plan(corpus)
    assert len(report.plans) == 3
    graph = _graph_from_plans(report.plans)
    chunk_ids = {plan.chunk_id for plan in report.plans}

    body = api(graph).post("/api/v1/c2/reasoning", json=REQUEST).json()
    [herb] = body["candidates"]
    assert herb["candidate_id"] == "H-PUNARNAVA"
    known = set(graph.evidence)
    cited = set(herb["supporting_evidence_ids"])
    assert cited and cited <= known
    for statement in herb["rationale"]:
        assert set(statement["evidence_ids"]) <= known
        assert set(statement["claim_ids"]) <= set(graph.claims)
    refs = [ref for path in herb["paths"] for step in path["claims"] for ref in step["supporting_evidence"]]
    assert refs and all(ref["source_chunk_id"] in chunk_ids for ref in refs)
    assert all(ref["source_id"] == "syn-samhita" for ref in refs)
    texts = {e["evidence_id"]: e["text"] for e in graph.evidence.values()}
    assert "triphalā\npunarnavā ca" in texts.values()
    assert all(ref["provenance_complete"] for ref in refs)
    assert body["medical_conclusion"] is None


def test_source_without_curated_metadata_is_not_promoted(tmp_path, monkeypatch):
    """Missing source metadata blocks promotion instead of inventing it."""
    raw, extracted = tmp_path / "raw", tmp_path / "extracted"
    raw.mkdir()
    make_tei(raw / "nometa.xml", SYNTHETIC_TEI_BODY)
    assert main(["manifest", str(raw), "--out", str(extracted / "manifest.json"),
                 "--extract-dir", str(extracted)]) == 0
    assert main(["chunk", str(extracted)]) == 0
    candidates = extracted / "candidates"
    assert main(["candidates-extract", str(extracted), "--out", str(candidates)]) == 0
    corpus = {"raw": raw, "extracted": extracted, "candidates": candidates}
    candidate = _symptom_candidate(candidates)
    _approve(candidates, candidate["claim_id"])
    report = _plan(corpus)
    assert report.plans == []
    assert any("title" in reason for _, reason in report.skipped)


def test_graph_outage_is_explicit_unavailable_not_fabricated_success(api):
    graph = FakeGraph()
    client = api(graph)
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr("app.api.c2.run_component2_reasoning",
                        MagicMock(side_effect=ServiceUnavailable("down")))
        response = client.post("/api/v1/c2/reasoning", json=REQUEST)
    assert response.status_code == 503
    assert response.json()["detail"] == {"status": "unavailable", "dependency": "knowledge_graph"}


def test_unknown_symptom_is_out_of_scope(api):
    body = api(FakeGraph()).post("/api/v1/c2/reasoning", json=REQUEST).json()
    assert body["sufficiency_status"] == "out_of_scope"
    assert body["candidates"] == [] and body["abstention"]["abstain"] is True
