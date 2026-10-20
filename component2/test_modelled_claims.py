"""Reviewer-modelled claims: validation, store integrity, promotion plans."""

import json

import pytest

from app.config import IngestionSettings
from app.db.source_repository import plan_modelled_promotions, plan_modelled_retractions
from app.knowledge_candidates.models import ReviewerRole
from app.knowledge_candidates.modelled import (
    ModelledClaim,
    ModelledClaimError,
    ModelledStore,
    model_claim,
)
from app.knowledge_ingestion.chunking import chunk_passages
from app.knowledge_ingestion.extractors import extract_document
from app.knowledge_ingestion.models import EvidenceCategory, SourceMetadata
from app.knowledge_ingestion.service import process_source
from ingestion_test_support import SYNTHETIC_TEI_BODY, make_tei


SETTINGS = IngestionSettings()
QUOTE = "triphalā\npunarnavā ca"


@pytest.fixture
def corpus(tmp_path):
    path = make_tei(tmp_path / "syn.xml", SYNTHETIC_TEI_BODY)
    metadata = SourceMetadata(source_id="syn", title="Synthetic", evidence_category=EvidenceCategory.TRADITIONAL_TEXT)
    record = process_source(path, "syn.xml", metadata=metadata).record
    passages = extract_document(path, SETTINGS).passages
    chunks = chunk_passages("syn", passages, SETTINGS)
    chunk = next(c for c in chunks if QUOTE in c.text)
    return {"record": record, "chunks": {c.chunk_id: c for c in chunks}, "chunk": chunk}


def _model(chunk, **overrides):
    values = dict(
        subject="TherapeuticPrinciple:TP-SYN:Synthetic principle", predicate="USES_HERB",
        object="Herb:H-PUNARNAVA:Punarnava", quote=QUOTE,
        statement="The principle uses Punarnava.", reviewer="Dr Test",
        reviewer_role=ReviewerRole.PRACTITIONER, note="Verse names punarnava.",
    )
    values.update(overrides)
    return model_claim(chunk, **values)


def test_valid_claim_copies_exact_quote_and_provenance(corpus):
    claim = _model(corpus["chunk"])
    passage = claim.passage
    assert passage.sentence == QUOTE
    assert corpus["chunk"].text[passage.sentence_start:passage.sentence_end] == QUOTE
    assert "Syn.6.16.3" in passage.citation_refs
    assert claim.modelled_id.startswith("mod-")
    # Deterministic identity for the same claim and passage.
    assert _model(corpus["chunk"]).modelled_id == claim.modelled_id


@pytest.mark.parametrize("overrides, message", [
    ({"quote": "punarnava is not here at all"}, "does not occur"),
    ({"quote": "short"}, "at least 10"),
    ({"predicate": "CONTAINS_INGREDIENT"}, "not a reasoning predicate"),
    ({"predicate": "TREATS"}, "not a reasoning predicate"),
    ({"subject": "Herb:H-X:X"}, "does not allow subject type"),
    ({"subject": "Principle:TP-1:x"}, "Concept type"),
    ({"object": "Herb:H-PUNARNAVA"}, "Type:ID:Label"),
    ({"note": " "}, "note"),
    ({"reviewer": ""}, "reviewer"),
])
def test_invalid_claims_are_refused(corpus, overrides, message):
    with pytest.raises(ModelledClaimError, match=message):
        _model(corpus["chunk"], **overrides)


def test_ambiguous_quote_is_refused(corpus):
    chunk = corpus["chunk"].model_copy(update={"text": corpus["chunk"].text + " " + QUOTE})
    with pytest.raises(ModelledClaimError, match="more than once"):
        _model(chunk)


def test_store_is_append_only_and_detects_tampering(tmp_path, corpus):
    store = ModelledStore(tmp_path)
    claim = _model(corpus["chunk"])
    store.add(claim)
    with pytest.raises(ModelledClaimError, match="already exists"):
        store.add(claim)
    store.withdraw(claim.modelled_id, "Dr Test", ReviewerRole.PRACTITIONER, "Misread verse.")
    assert [e.action.value for e in store.load_log()] == ["active", "withdrawn"]
    # Editing the status without an event is rejected on load.
    row = json.loads(store.claims_path.read_text(encoding="utf-8"))
    row["status"] = "active"
    with pytest.raises(ValueError):
        ModelledClaim.model_validate(row)


def test_promotion_plan_and_its_guards(tmp_path, corpus):
    store = ModelledStore(tmp_path)
    claim = _model(corpus["chunk"])
    store.add(claim)
    sources = {"syn": corpus["record"]}
    report = plan_modelled_promotions(store.load().values(), sources, corpus["chunks"],
                                      modelled_log=store.load_log())
    [plan] = report.plans
    assert plan.triple == ("TP-SYN", "USES_HERB", "H-PUNARNAVA")
    assert plan.claim_properties["verification_status"] == "practitioner_verified"
    assert plan.claim_properties["modelled"] is True
    assert plan.evidence_properties["text"] == QUOTE
    assert {c.label for c in plan.concepts} == {"TherapeuticPrinciple", "Herb"}

    # Creation event missing from the append-only log.
    assert plan_modelled_promotions([claim], sources, corpus["chunks"], modelled_log=[]).skipped
    # Source without curated metadata.
    bare = corpus["record"].model_copy(update={"metadata": SourceMetadata()})
    [(_, reason)] = plan_modelled_promotions([claim], {"syn": bare}, corpus["chunks"]).skipped
    assert "title" in reason
    # Chunk text changed under the quote.
    changed = {cid: c.model_copy(update={"text": c.text.replace("triphalā", "xxxxxxxx")})
               for cid, c in corpus["chunks"].items()}
    [(_, reason)] = plan_modelled_promotions([claim], sources, changed).skipped
    assert "stale" in reason


def test_withdrawn_claims_are_not_promoted_but_retracted(tmp_path, corpus):
    store = ModelledStore(tmp_path)
    claim = _model(corpus["chunk"])
    store.add(claim)
    store.withdraw(claim.modelled_id, "Dr Test", ReviewerRole.PRACTITIONER, "Misread verse.")
    claims = store.load().values()
    report = plan_modelled_promotions(claims, {"syn": corpus["record"]}, corpus["chunks"])
    assert report.plans == [] and "withdrawn" in report.skipped[0][1]
    [retraction] = plan_modelled_retractions(claims).plans
    assert retraction.claim_id == f"CL-{claim.modelled_id}"
    assert "Misread verse." in retraction.reason
