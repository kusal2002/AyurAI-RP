import json
from datetime import datetime, timezone

import pytest
from neo4j.exceptions import ServiceUnavailable

from app.config import IngestionSettings
from app.db.schema import SOURCE_SCHEMA_STATEMENTS, initialize_source_schema
from app.db.source_repository import (
    PromotionError,
    make_evidence_id,
    plan_promotions,
    promote,
)
from app.knowledge_candidates.extractor import LexiconCueExtractor
from app.knowledge_candidates.lexicon import Lexicon, LexiconMatcher
from app.knowledge_candidates.models import ReviewerRole, ReviewStatus
from app.knowledge_candidates.review import review_candidate
from app.knowledge_ingestion.chunking import chunk_passages
from app.knowledge_ingestion.cli import main
from app.knowledge_ingestion.models import (
    EvidenceCategory,
    ExtractedPassage,
    ExtractionStatus,
    PassageKind,
    SourceFormat,
    SourceLocation,
    SourceMetadata,
    SourceRecord,
)
from app.ontology.relationships import (
    DESCRIPTIVE_RELATIONSHIP_RULES,
    RELATIONSHIP_RULES,
    validate_relationship,
)
from app.reasoning.knowledge_chain import trace_knowledge_chains
from c2_test_support import build_pandu_graph


LEXICON = Lexicon.model_validate({
    "lexicon_version": "test-1", "review_status": "test", "concepts": [
        {"concept_id": "R-PANDU", "concept_type": "Roga", "label": "Pandu",
         "terms": ["pandu"]},
        {"concept_id": "S-PALLOR", "concept_type": "Symptom", "label": "pallor",
         "terms": ["pallor"]},
        {"concept_id": "H-PUNARNAVA", "concept_type": "Herb", "label": "Punarnava",
         "terms": ["punarnava"]},
        {"concept_id": "H-HARITAKI", "concept_type": "Herb", "label": "Haritaki",
         "terms": ["haritaki"]},
        {"concept_id": "F-TRIPHALA", "concept_type": "Formulation", "label": "Triphala",
         "terms": ["triphala"]},
    ]})
EXTRACTOR = LexiconCueExtractor(LexiconMatcher(LEXICON))
SOURCE_ID = "charaka-test-ed"
SENTENCE = "Pallor is a symptom of pandu."
TEXT = (
    f"{SENTENCE} Punarnava is indicated in pandu. "
    "Triphala is composed of haritaki. Private book wording continues here."
)


def source_record(**metadata):
    defaults = {
        "source_id": SOURCE_ID, "title": "Synthetic Samhita", "edition": "2011",
        "evidence_category": EvidenceCategory.TRADITIONAL_TEXT,
        "source_language": "sa", "translation_language": "en",
    }
    defaults.update(metadata)
    return SourceRecord(
        source_id=SOURCE_ID, source_id_origin="metadata", file_name="book.pdf",
        relative_path="book.pdf", source_format=SourceFormat.PDF,
        file_size_bytes=10, content_sha256="a" * 64,
        metadata=SourceMetadata(**defaults),
        extraction_status=ExtractionStatus.EXTRACTED, extractor="pypdf",
        extractor_version="6", extracted_at=datetime.now(timezone.utc),
        passage_count=1,
    )


def chunks():
    passage = ExtractedPassage(
        passage_index=0, kind=PassageKind.PAGE, text=TEXT,
        location=SourceLocation(page=12),
    )
    return chunk_passages(
        SOURCE_ID, [passage],
        IngestionSettings(chunk_max_chars=800, chunk_overlap_chars=0),
    )


def candidates(approve=("HAS_SYMPTOM", "CONTAINS_INGREDIENT", "TRADITIONALLY_INDICATED_FOR"),
               role=ReviewerRole.PRACTITIONER):
    chunk = chunks()[0]
    _, found = EXTRACTOR.extract(chunk, EvidenceCategory.TRADITIONAL_TEXT)
    result = {}
    for candidate in found:
        if candidate.predicate in approve:
            candidate, _, _ = review_candidate(
                candidate, ReviewStatus.APPROVED, "ana", role
            )
        result[candidate.claim_id] = candidate
    return result


def plan(cands=None, source=None, chunk_map=None):
    cands = candidates() if cands is None else cands
    chunk_map = {c.chunk_id: c for c in chunks()} if chunk_map is None else chunk_map
    return plan_promotions(
        cands.values(), {}, {SOURCE_ID: source or source_record()}, chunk_map
    )


def plan_for(report, predicate):
    return next(p for p in report.plans if p.triple[1] == predicate)


# --- fake driver -------------------------------------------------------------

class FakeCounters:
    def __init__(self, nodes=0):
        self.nodes_created = nodes
        self.relationships_created = 0
        self.properties_set = 0
        self.labels_added = 0
        self.labels_removed = 0
        self.nodes_deleted = 0
        self.relationships_deleted = 0


class FakeResult:
    def __init__(self, records, counters):
        self._records = records
        self._counters = counters

    def __iter__(self):
        return iter(self._records)

    def consume(self):
        return type("Summary", (), {"counters": self._counters})()


class FakeTx:
    """Records Cypher; emulates just enough state for these queries.

    State changes (MERGE keys, source hashes, promoted claims) are staged
    and only become visible when the transaction function returns.
    """

    def __init__(self, driver):
        self.driver = driver
        self.ops = []
        self.new_keys = set()
        self.source_hashes = {}
        self.claims = set()

    def run(self, query, **params):
        self.ops.append((query, params))
        if self.driver.raise_in_tx and "MERGE (claim:Claim" in query:
            raise self.driver.raise_in_tx
        key = (query.split("{")[0].strip(), json.dumps(
            {k: v for k, v in params.items() if k.endswith("_id") and k != "batch_id"},
            sort_keys=True))
        created = key not in self.driver.keys and key not in self.new_keys
        self.new_keys.add(key)
        records = []
        if "MERGE (s:Source" in query:
            known = {**self.driver.source_hashes, **self.source_hashes}
            stored = known.get(params["source_id"], params["content_sha256"])
            if stored == params["content_sha256"]:
                self.source_hashes[params["source_id"]] = stored
                records = [{"source_id": params["source_id"]}]
        elif "RETURN claim.claim_id" in query and "REMOVE claim:Claim" not in query:
            if not self.driver.fail_claim_link:
                self.claims.add(params["claim_id"])
                records = [{"claim_id": params["claim_id"]}]
        elif "REMOVE claim:Claim" in query:
            if params["claim_id"] in self.driver.claims:
                records = [{"claim_id": params["claim_id"]}]
        elif "evidence_retracted" in query:
            records = [{"evidence_retracted": 1}]
        return FakeResult(records, FakeCounters(nodes=int(created)))


class FakeSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        self.driver.statements.append(query)
        return FakeResult([], FakeCounters())

    def execute_write(self, work, *args):
        tx = FakeTx(self.driver)
        self.driver.transactions += 1
        result = work(tx, *args)  # an exception discards everything (rollback)
        self.driver.committed.extend(tx.ops)
        self.driver.keys |= tx.new_keys
        self.driver.source_hashes.update(tx.source_hashes)
        self.driver.claims |= tx.claims
        return result


class FakeDriver:
    def __init__(self, fail_claim_link=False, unavailable=False, raise_in_tx=None):
        self.fail_claim_link = fail_claim_link
        self.unavailable = unavailable
        self.raise_in_tx = raise_in_tx
        self.committed = []
        self.statements = []
        self.keys = set()
        self.source_hashes = {}
        self.claims = set()
        self.transactions = 0

    def session(self, **kwargs):
        if self.unavailable:
            raise ServiceUnavailable("connection refused")
        return FakeSession(self)


class ExplodingDriver:
    def session(self, **kwargs):
        raise AssertionError("dry run must not touch the database")


# --- schema ------------------------------------------------------------------

def test_source_schema_dry_run_touches_nothing():
    statements = initialize_source_schema(driver=ExplodingDriver())
    assert statements == list(SOURCE_SCHEMA_STATEMENTS)
    assert len(statements) == 7
    joined = " ".join(statements)
    assert ":DescriptiveEvidence" in joined and ":RetractedClaim" in joined
    for statement in statements:
        assert "IF NOT EXISTS" in statement
        assert "DROP" not in statement.upper()


def test_source_schema_apply_runs_additive_statements():
    driver = FakeDriver()
    initialize_source_schema(driver=driver, dry_run=False)
    assert driver.statements == list(SOURCE_SCHEMA_STATEMENTS)


# --- ontology v1.1 -----------------------------------------------------------

def test_contains_ingredient_is_descriptive_only():
    assert "CONTAINS_INGREDIENT" not in RELATIONSHIP_RULES
    assert "CONTAINS_INGREDIENT" in DESCRIPTIVE_RELATIONSHIP_RULES
    with pytest.raises(ValueError):
        validate_relationship("CONTAINS_INGREDIENT", "Formulation", "Herb")
    validate_relationship("CONTAINS_INGREDIENT", "Formulation", "Herb",
                          allow_descriptive=True)


def test_reasoning_chains_ignore_descriptive_claims():
    plain = build_pandu_graph()
    with plain.patched():
        expected = trace_knowledge_chains("R-PANDU")

    graph = build_pandu_graph()
    graph.add_concept("Herb", "H-INGREDIENT", "ingredient")
    graph.add_claim("CL-ING", "F-1", "CONTAINS_INGREDIENT", "H-INGREDIENT")
    with graph.patched():
        actual = trace_knowledge_chains("R-PANDU")

    assert actual == expected
    assert "CONTAINS_INGREDIENT" not in json.dumps(actual, default=str)


# --- planning ----------------------------------------------------------------

def test_plan_maps_approved_candidates_with_provenance():
    report = plan()

    symptom = plan_for(report, "INDICATES")
    assert symptom.triple == ("S-PALLOR", "INDICATES", "R-PANDU")
    evidence = symptom.evidence_properties
    assert evidence["text"] == SENTENCE
    assert evidence["evidence_type"] == "classical"
    assert evidence["title"] == "Synthetic Samhita"
    assert evidence["source_name"] == "Synthetic Samhita (2011)"
    assert evidence["page"] == "12"
    assert evidence["practitioner_verified"] is True
    assert evidence["evidence_id"] == make_evidence_id(
        symptom.chunk_id, *symptom.sentence_span
    )
    claim = symptom.claim_properties
    assert claim["verification_status"] == "practitioner_verified"
    assert claim["approved_by"] == "ana" and claim["candidate_id"] == symptom.candidate_id
    assert "confidence" not in claim  # null is not written
    assert "created_at" not in claim  # set once, on create, by the query
    assert claim["descriptive"] is False
    assert symptom.evidence_label == "Evidence"

    ingredient = plan_for(report, "CONTAINS_INGREDIENT")
    assert ingredient.triple == ("F-TRIPHALA", "CONTAINS_INGREDIENT", "H-HARITAKI")


def test_plan_does_not_upload_book_text():
    for item in plan().plans:
        assert "text" not in item.chunk_properties
        assert "original_text" not in item.chunk_properties
        assert "Private book wording" not in json.dumps(item.chunk_properties)
        assert "Private book wording" not in json.dumps(item.source_properties)
        assert "Private book wording" not in item.evidence_properties["text"]
        assert all(v is not None for v in item.source_properties.values())


def test_plan_skips_with_reasons():
    report = plan(candidates(approve=("HAS_SYMPTOM", "TRADITIONALLY_INDICATED_FOR")))
    reasons = dict(report.skipped)
    assert any("no direct ontology mapping" in r for r in reasons.values())
    assert any(r.startswith("not approved") for r in reasons.values())

    def only_reason(**kwargs):
        rep = plan(candidates(approve=("HAS_SYMPTOM",)), **kwargs)
        assert rep.plans == []
        return {r for _, r in rep.skipped if not r.startswith("not approved")}

    assert only_reason(source=source_record(title=None)) == {
        "source metadata has no title (add a .meta.json sidecar)"}
    assert only_reason(source=source_record(evidence_category=None)) == {
        "source evidence_category not declared"}
    assert only_reason(source=source_record(evidence_category=EvidenceCategory.OTHER)) == {
        "evidence_category 'other' has no evidence type mapping"}
    assert only_reason(chunk_map={}) == {
        "supporting chunk not found (re-chunk and re-extract)"}


def test_stale_and_researcher_approvals():
    cands = candidates(approve=("HAS_SYMPTOM",), role=ReviewerRole.RESEARCHER)
    report = plan(cands)
    assert plan_for(report, "INDICATES").claim_properties["verification_status"] == (
        "literature_supported")
    assert plan_for(report, "INDICATES").evidence_properties["practitioner_verified"] is False

    stale = {k: v.model_copy(update={"stale": True}) for k, v in cands.items()}
    assert plan(stale).plans == []
    assert "stale" in dict(plan(stale).skipped).values()


def test_plans_are_deterministic():
    first, second = plan(), plan()
    assert [(p.claim_id, p.evidence_properties["evidence_id"]) for p in first.plans] == [
        (p.claim_id, p.evidence_properties["evidence_id"]) for p in second.plans
    ]


# --- writes ------------------------------------------------------------------

def test_dry_run_never_touches_database():
    report = promote(plan(), driver=ExplodingDriver(), apply=False)
    assert report.applied is False
    assert report.batch_id.startswith("promo-")


def test_apply_writes_one_transaction_per_claim_with_merge_only():
    report = plan()
    driver = FakeDriver()
    promote(report, driver=driver, apply=True, batch_id="promo-test")

    assert report.applied and driver.transactions == len(report.plans) == 2
    for query, params in driver.committed:
        upper = query.upper()
        assert "MERGE" in upper or "MATCH" in upper
        assert "DELETE" not in upper and "DETACH" not in upper
        assert " CREATE " not in upper.replace("ON CREATE", "")
        # Values travel as parameters, never inside the Cypher text.
        assert SENTENCE not in query and SOURCE_ID not in query
    labels = " ".join(q for q, _ in driver.committed)
    assert ":Roga" in labels and ":Symptom" in labels and ":Claim" in labels
    assert report.counters["nodes_created"] > 0


def test_apply_is_idempotent():
    driver = FakeDriver()
    promote(plan(), driver=driver, apply=True, batch_id="b1")
    again = promote(plan(), driver=driver, apply=True, batch_id="b2")
    assert again.counters["nodes_created"] == 0


def test_failed_link_rolls_back_the_whole_claim():
    driver = FakeDriver(fail_claim_link=True)
    with pytest.raises(PromotionError):
        promote(plan(), driver=driver, apply=True)
    assert driver.committed == []


def test_database_unavailable_is_reported_safely():
    with pytest.raises(PromotionError, match="unavailable") as info:
        promote(plan(), driver=FakeDriver(unavailable=True), apply=True)
    assert "connection refused" not in str(info.value)


# --- CLI ---------------------------------------------------------------------

def test_cli_source_schema_and_promote_dry_run(tmp_path, capsys, monkeypatch):
    def forbid_driver():
        raise AssertionError("dry run must not connect")

    monkeypatch.setattr("app.db.neo4j.get_neo4j_driver", forbid_driver)
    monkeypatch.setattr("app.db.source_repository.get_neo4j_driver", forbid_driver)

    assert main(["source-schema"]) == 0
    output = capsys.readouterr().out
    assert "DRY RUN" in output and "source_id_unique" in output

    book = tmp_path / "book.md"
    book.write_text(f"# Pandu\n\n{SENTENCE}", encoding="utf-8")
    (tmp_path / "book.md.meta.json").write_text(json.dumps({
        "source_id": "book-ed1", "title": "Synthetic Book",
        "evidence_category": "traditional_text",
    }), encoding="utf-8")
    from app.knowledge_ingestion.service import process_source, write_extraction
    out = tmp_path / "extracted"
    write_extraction(process_source(book), out)
    assert main(["chunk", str(out)]) == 0
    store = tmp_path / "cand"
    lexicon = tmp_path / "lex.json"
    lexicon.write_text(LEXICON.model_dump_json(), encoding="utf-8")
    assert main(["candidates-extract", str(out), "--out", str(store),
                 "--lexicon", str(lexicon)]) == 0
    from app.knowledge_candidates.store import CandidateStore
    claim_id = next(iter(CandidateStore(store).load_candidates()))
    assert main(["review", str(store), claim_id, "--status", "approved",
                 "--reviewer", "ana", "--role", "researcher"]) == 0
    capsys.readouterr()

    assert main(["promote", str(store), "--extracted", str(out)]) == 0
    output = capsys.readouterr().out
    assert "to promote: 1" in output
    assert "S-PALLOR -INDICATES-> R-PANDU [literature_supported]" in output
    assert "DRY RUN: nothing was written" in output


# --- audit fixes -------------------------------------------------------------

from neo4j.exceptions import ClientError  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.db.source_repository import (  # noqa: E402
    DESCRIPTIVE_EVIDENCE_LABEL,
    plan_retractions,
    retract,
)
from app.knowledge_candidates.models import CandidateClaim  # noqa: E402


def symptom_candidate(**kwargs):
    return next(c for c in candidates(**kwargs).values()
                if c.predicate == "HAS_SYMPTOM")


def test_rejected_candidates_are_never_promoted():
    rejected = {}
    for claim_id, candidate in candidates(approve=()).items():
        candidate, _, _ = review_candidate(
            candidate, ReviewStatus.REJECTED, "ana", ReviewerRole.RESEARCHER,
            note="Misreading of the sentence.",
        )
        rejected[claim_id] = candidate
    report = plan(rejected)
    assert report.plans == []
    assert {reason for _, reason in report.skipped} == {"not approved (rejected)"}


def test_withdrawn_approval_is_not_promoted():
    approved = symptom_candidate()
    withdrawn, _, _ = review_candidate(
        approved, ReviewStatus.REJECTED, "ben", ReviewerRole.PRACTITIONER,
        note="Translation is wrong.",
    )
    assert plan({withdrawn.claim_id: withdrawn}).plans == []


def test_approved_status_without_event_is_skipped_not_crashing():
    unreviewed = symptom_candidate(approve=())
    forged = unreviewed.model_copy(update={"review_status": ReviewStatus.APPROVED})
    report = plan({forged.claim_id: forged})
    assert report.plans == []
    assert report.skipped == [
        (forged.claim_id, "approved status has no matching approval event")
    ]


def test_inconsistent_review_history_cannot_be_loaded():
    unreviewed = symptom_candidate(approve=())
    data = unreviewed.model_dump(mode="json")
    data["review_status"] = "approved"
    with pytest.raises(ValidationError, match="review history"):
        CandidateClaim.model_validate(data)

    approved = symptom_candidate()
    data = approved.model_dump(mode="json")
    data["review_history"][0]["claim_id"] = "cand-other"
    with pytest.raises(ValidationError):
        CandidateClaim.model_validate(data)


def test_approval_must_be_in_review_log_when_given():
    approved = symptom_candidate()
    cands = {approved.claim_id: approved}
    sources = {SOURCE_ID: source_record()}
    chunk_map = {c.chunk_id: c for c in chunks()}

    unlogged = plan_promotions(cands.values(), {}, sources, chunk_map, review_log=[])
    assert unlogged.plans == []
    assert unlogged.skipped == [
        (approved.claim_id, "approval event not found in review_log.jsonl")
    ]
    logged = plan_promotions(
        cands.values(), {}, sources, chunk_map,
        review_log=list(approved.review_history),
    )
    assert len(logged.plans) == 1


def test_manifest_source_conflicts_block_promotion():
    report = plan_promotions(
        candidates().values(), {}, {SOURCE_ID: source_record()},
        {c.chunk_id: c for c in chunks()}, conflicting_source_ids={SOURCE_ID},
    )
    assert report.plans == []
    assert "source_id is reused for different file content (see manifest)" in {
        reason for _, reason in report.skipped
    }


def test_write_time_source_hash_conflict_rolls_back():
    driver = FakeDriver()
    driver.source_hashes[SOURCE_ID] = "b" * 64  # stored from another file
    with pytest.raises(PromotionError, match="different file content"):
        promote(plan(), driver=driver, apply=True)
    assert driver.committed == []


def test_created_at_is_set_on_create_only():
    driver = FakeDriver()
    promote(plan(), driver=driver, apply=True, batch_id="b1")
    claim_queries = [q for q, _ in driver.committed if "MERGE (claim:Claim" in q]
    assert claim_queries
    for query in claim_queries:
        assert "ON CREATE SET claim.promotion_batch_id = $batch_id, claim.created_at = $now" in query
    for _, params in driver.committed:
        assert "created_at" not in params.get("properties", {})


def test_descriptive_evidence_stays_out_of_the_api_evidence_index():
    report = plan()
    ingredient = plan_for(report, "CONTAINS_INGREDIENT")
    assert ingredient.descriptive is True
    assert ingredient.evidence_label == DESCRIPTIVE_EVIDENCE_LABEL
    assert ingredient.evidence_properties["evidence_id"].startswith("DEV-")
    assert ingredient.claim_properties["descriptive"] is True

    driver = FakeDriver()
    promote(report, driver=driver, apply=True)
    for query, params in driver.committed:
        if params.get("evidence_id") == ingredient.evidence_properties["evidence_id"]:
            assert "(e:Evidence " not in query and ":Evidence {" not in query

    # The API evidence index loads exactly the :Evidence label.
    import inspect
    from app.db import repository
    source = inspect.getsource(repository.list_evidence)
    assert "MATCH (e:Evidence)" in source
    assert DESCRIPTIVE_EVIDENCE_LABEL not in source


def test_neo4j_error_inside_transaction_is_reported_and_rolled_back():
    driver = FakeDriver(raise_in_tx=ClientError("constraint violated"))
    with pytest.raises(PromotionError, match="rejected a transaction") as info:
        promote(plan(), driver=driver, apply=True)
    assert "constraint violated" not in str(info.value)
    assert driver.committed == []


# --- retraction --------------------------------------------------------------

def test_retraction_plan_covers_withdrawn_and_stale_approvals_only():
    approved = symptom_candidate()
    withdrawn, _, _ = review_candidate(
        approved, ReviewStatus.UNCERTAIN, "ben", ReviewerRole.PRACTITIONER,
        note="Check the commentary.",
    )
    stale = symptom_candidate().model_copy(update={"stale": True})
    never = symptom_candidate(approve=())
    unmappable = next(c for c in candidates().values()
                      if c.predicate == "TRADITIONALLY_INDICATED_FOR")

    # One version per candidate, as in a real store.
    report = plan_retractions([withdrawn, never, unmappable])
    assert [(p.claim_id, p.retracted_by) for p in report.plans] == [
        (f"CL-{withdrawn.claim_id}", "ben")
    ]
    assert "uncertain" in report.plans[0].reason

    stale_report = plan_retractions([stale])
    assert stale_report.plans[0].retracted_by == "system:stale"


def test_retraction_dry_run_and_apply_never_delete():
    approved = symptom_candidate()
    withdrawn, _, _ = review_candidate(
        approved, ReviewStatus.REJECTED, "ben", ReviewerRole.PRACTITIONER,
        note="Wrong reading.",
    )
    report = plan_retractions([withdrawn])
    assert retract(report, driver=ExplodingDriver(), apply=False).applied is False

    driver = FakeDriver()
    promote(plan({approved.claim_id: approved}), driver=driver, apply=True)
    retract(report, driver=driver, apply=True)
    assert report.retracted_claims == [f"CL-{approved.claim_id}"]
    assert report.evidence_retracted == 1
    for query, _ in driver.committed:
        upper = query.upper()
        assert "DELETE" not in upper and "DETACH" not in upper

    missing = plan_retractions([withdrawn])
    retract(missing, driver=FakeDriver(), apply=True)
    assert missing.not_in_graph == [f"CL-{approved.claim_id}"]


def test_repromotion_restores_retracted_nodes():
    driver = FakeDriver()
    promote(plan(), driver=driver, apply=True)
    claim_query = next(q for q, _ in driver.committed if "MERGE (claim:Claim" in q)
    evidence_query = next(q for q, _ in driver.committed if "FROM_CHUNK" in q)
    assert "REMOVE x:RetractedClaim SET x:Claim" in claim_query
    assert "REMOVE x:RetractedEvidence" in evidence_query


def test_cli_retract_dry_run(tmp_path, capsys, monkeypatch):
    from app.knowledge_candidates.store import CandidateStore

    def forbid_driver():
        raise AssertionError("dry run must not connect")

    monkeypatch.setattr("app.db.source_repository.get_neo4j_driver", forbid_driver)
    approved = symptom_candidate()
    withdrawn, event, _ = review_candidate(
        approved, ReviewStatus.REJECTED, "ben", ReviewerRole.PRACTITIONER,
        note="Wrong reading.",
    )
    store = CandidateStore(tmp_path / "cand")
    store.save({withdrawn.claim_id: withdrawn}, {})
    assert main(["retract", str(tmp_path / "cand")]) == 0
    output = capsys.readouterr().out
    assert "Claims to retract: 1" in output and "DRY RUN" in output


def test_connection_script_does_not_connect_on_import(monkeypatch):
    import importlib
    import sys

    import neo4j

    def forbid(*args, **kwargs):
        raise AssertionError("importing must not open a connection")

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", forbid)
    sys.modules.pop("test_neo4j_connection", None)
    module = importlib.import_module("test_neo4j_connection")
    assert callable(module.main)


# --- qualified statements (extractor v4) -------------------------------------

def test_qualified_statement_flag_is_carried_to_promoted_claims():
    qualified_text = (
        "During the period of an early author, Triphala was composed of one "
        "part of haritaki. Pallor is a symptom of pandu."
    )
    passage = ExtractedPassage(
        passage_index=0, kind=PassageKind.PAGE, text=qualified_text,
        location=SourceLocation(page=3),
    )
    (chunk,) = chunk_passages(
        SOURCE_ID, [passage],
        IngestionSettings(chunk_max_chars=800, chunk_overlap_chars=0),
    )
    _, found = EXTRACTOR.extract(chunk, EvidenceCategory.TRADITIONAL_TEXT)
    approved = {}
    for candidate in found:
        candidate, _, _ = review_candidate(
            candidate, ReviewStatus.APPROVED, "reviewer-under-test",
            ReviewerRole.RESEARCHER, note="test-only approval",
        )
        approved[candidate.claim_id] = candidate

    report = plan_promotions(
        approved.values(), {}, {SOURCE_ID: source_record()}, {chunk.chunk_id: chunk}
    )
    by_predicate = {p.triple[1]: p for p in report.plans}
    ingredient = by_predicate["CONTAINS_INGREDIENT"]
    assert ingredient.claim_properties["qualified_statement"] is True
    assert "During the period of an early author" in ingredient.evidence_properties["text"]
    assert by_predicate["INDICATES"].claim_properties["qualified_statement"] is False
