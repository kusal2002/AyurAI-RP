import json

import pytest
from pydantic import ValidationError

from app.config import IngestionSettings
from app.knowledge_candidates.conflicts import attach_conflicts, detect_conflicts
from app.knowledge_candidates.extractor import (
    MAX_CANDIDATES_PER_SENTENCE,
    LexiconCueExtractor,
)
from app.knowledge_candidates.lexicon import (
    DEFAULT_LEXICON_PATH,
    Lexicon,
    LexiconMatcher,
    load_lexicon,
)
from app.knowledge_candidates.models import (
    AMBIGUOUS_TERM,
    COMPOUND_MATCH,
    DOSAGE_STATEMENT,
    EVIDENCE_CATEGORY_UNKNOWN,
    NEGATION_CUE,
    CandidateClaim,
    ConceptRef,
    ConflictKind,
    ConflictStatus,
    ReviewerRole,
    ReviewStatus,
)
from app.knowledge_candidates.review import (
    ReviewError,
    TrustBoundaryError,
    review_candidate,
    to_ontology_claim,
    trusted_candidates,
)
from app.knowledge_candidates.store import CandidateStore, run_extraction
from app.knowledge_ingestion.chunking import chunk_passages
from app.knowledge_ingestion.cli import main
from app.knowledge_ingestion.models import (
    EvidenceCategory,
    ExtractedPassage,
    PassageKind,
    SourceLocation,
    SourceMetadata,
)
from app.knowledge_ingestion.service import process_source, write_extraction
from app.models.claim import VerificationStatus


LEXICON = Lexicon.model_validate(
    {
        "lexicon_version": "test-1",
        "review_status": "test",
        "concepts": [
            {"concept_id": "R-PANDU", "concept_type": "Roga", "label": "Pandu",
             "allow_compound": True, "terms": ["pandu", "pāṇḍu", "पाण्डु"]},
            {"concept_id": "S-PALLOR", "concept_type": "Symptom", "label": "pallor",
             "terms": ["pallor"]},
            {"concept_id": "H-PUNARNAVA", "concept_type": "Herb", "label": "Punarnava",
             "terms": ["punarnava", "पुनर्नवा"]},
            {"concept_id": "F-TRIPHALA", "concept_type": "Formulation", "label": "Triphala",
             "terms": ["triphala"]},
            {"concept_id": "DO-PITTA", "concept_type": "Dosha", "label": "Pitta",
             "allow_compound": True, "ambiguous": True, "terms": ["pitta"]},
        ],
    }
)
EXTRACTOR = LexiconCueExtractor(LexiconMatcher(LEXICON))


def chunks_for(texts, source_id="src-book", page=1):
    passages = [
        ExtractedPassage(
            passage_index=i, kind=PassageKind.PAGE, text=text,
            location=SourceLocation(page=page + i),
        )
        for i, text in enumerate(texts)
    ]
    return chunk_passages(
        source_id, passages,
        IngestionSettings(chunk_max_chars=800, chunk_overlap_chars=0),
        SourceMetadata(source_language="sa", translation_language="en"),
    )


def extract(text, category=EvidenceCategory.TRADITIONAL_TEXT, **kwargs):
    chunk = chunks_for([text], **kwargs)[0]
    return EXTRACTOR.extract(chunk, category)


def by_predicate(candidates):
    return {
        (c.subject.concept_id, c.predicate, c.object.concept_id): c
        for c in candidates
    }


# --- lexicon -----------------------------------------------------------------

def test_seed_lexicon_loads_and_is_marked_unreviewed():
    lexicon = load_lexicon(DEFAULT_LEXICON_PATH)
    assert lexicon.review_status == "unreviewed_seed"
    ids = {c.concept_id for c in lexicon.concepts}
    assert {"R-PANDU", "H-PUNARNAVA", "F-TRIPHALA"} <= ids
    pandu = next(c for c in lexicon.concepts if c.concept_id == "R-PANDU")
    assert "anaemia" not in pandu.terms and "anemia" not in pandu.terms


def test_lexicon_rejects_shared_terms_and_unknown_types():
    with pytest.raises(ValidationError):
        Lexicon.model_validate({
            "lexicon_version": "x", "review_status": "x", "concepts": [
                {"concept_id": "A", "concept_type": "Herb", "label": "a", "terms": ["same"]},
                {"concept_id": "B", "concept_type": "Herb", "label": "b", "terms": ["Same"]},
            ]})
    with pytest.raises(ValidationError):
        Lexicon.model_validate({
            "lexicon_version": "x", "review_status": "x", "concepts": [
                {"concept_id": "A", "concept_type": "Disease", "label": "a", "terms": ["a"]},
            ]})


def test_matcher_respects_word_boundaries_and_compounds():
    matcher = LexiconMatcher(LEXICON)
    found = {(m.concept.concept_id, m.surface, m.compound)
             for m in matcher.find("Pāṇḍuroga and expandu and triphalachurna and Triphala.")}
    assert ("R-PANDU", "Pāṇḍu", True) in found
    assert ("F-TRIPHALA", "Triphala", False) in found
    assert not any(surface == "pandu" for _, surface, _ in found)  # inside 'expandu'
    assert len([f for f in found if f[0] == "F-TRIPHALA"]) == 1  # no compound match


# --- extraction --------------------------------------------------------------

def test_cue_produces_typed_traceable_candidate():
    mentions, candidates = extract(
        "Punarnava is indicated in pandu. Pallor is a symptom of pandu."
    )

    relations = by_predicate(candidates)
    indicated = relations[("H-PUNARNAVA", "TRADITIONALLY_INDICATED_FOR", "R-PANDU")]
    assert indicated.cue == "indicated in"
    assert indicated.passage.sentence == "Punarnava is indicated in pandu."
    assert indicated.passage.page_start == 1
    assert indicated.passage.declared_source_language == "sa"
    assert indicated.evidence_category == EvidenceCategory.TRADITIONAL_TEXT
    assert indicated.extraction_confidence is None
    assert indicated.review_status == ReviewStatus.CANDIDATE
    assert indicated.uncertainty == []
    assert ("R-PANDU", "HAS_SYMPTOM", "S-PALLOR") in relations
    assert {m.concept.concept_id for m in mentions.mentions} == {
        "H-PUNARNAVA", "R-PANDU", "S-PALLOR"
    }


def test_cooccurrence_without_cue_is_only_a_mention():
    mentions, candidates = extract("Punarnava and pandu appear in this list.")
    assert candidates == []
    assert len(mentions.mentions) == 2


def test_devanagari_sentence_with_cue():
    _, candidates = extract("पाण्डुरोगे पुनर्नवा हिता ॥ १ ॥")
    candidate = by_predicate(candidates)[
        ("H-PUNARNAVA", "TRADITIONALLY_INDICATED_FOR", "R-PANDU")
    ]
    assert COMPOUND_MATCH in candidate.uncertainty
    assert candidate.passage.verse_numbers == ["1"]


def test_negation_dosage_and_unknown_category_are_noted_not_interpreted():
    _, candidates = extract(
        "Triphala should not be used in pandu; the dose is 3 g.", category=None
    )
    caution = by_predicate(candidates)[("F-TRIPHALA", "HAS_CAUTION", "R-PANDU")]
    assert NEGATION_CUE in caution.uncertainty
    assert DOSAGE_STATEMENT in caution.uncertainty
    assert EVIDENCE_CATEGORY_UNKNOWN in caution.uncertainty
    assert caution.evidence_category is None


def test_ambiguous_terms_are_noted():
    _, candidates = extract("Pandu is caused by vitiated pitta.")
    dosha = by_predicate(candidates)[("R-PANDU", "ASSOCIATED_WITH_DOSHA", "DO-PITTA")]
    assert AMBIGUOUS_TERM in dosha.uncertainty


def test_claim_ids_are_stable():
    text = "Punarnava is indicated in pandu."
    first = [c.claim_id for c in extract(text)[1]]
    again = [c.claim_id for c in extract(text)[1]]
    other_source = [c.claim_id for c in extract(text, source_id="src-other")[1]]
    assert first == again
    assert not set(first) & set(other_source)


def test_candidates_per_sentence_are_capped():
    herbs = [
        {"concept_id": f"H-{i}", "concept_type": "Herb", "label": f"herb{i}",
         "terms": [f"herb{i}"]}
        for i in range(10)
    ]
    rogas = [
        {"concept_id": f"R-{i}", "concept_type": "Roga", "label": f"roga{i}",
         "terms": [f"roga{i}"]}
        for i in range(5)
    ]
    lexicon = Lexicon.model_validate(
        {"lexicon_version": "t", "review_status": "t", "concepts": herbs + rogas}
    )
    text = " ".join(f"herb{i}" for i in range(10)) + " are useful in " + " ".join(
        f"roga{i}" for i in range(5)
    ) + "."
    chunk = chunks_for([text])[0]
    _, candidates = LexiconCueExtractor(LexiconMatcher(lexicon)).extract(chunk)
    assert len(candidates) == MAX_CANDIDATES_PER_SENTENCE


def test_candidate_schema_rejects_wrong_types_and_fake_confidence():
    _, candidates = extract("Punarnava is indicated in pandu.")
    data = candidates[0].model_dump()
    data["subject"] = ConceptRef(concept_id="S-PALLOR", concept_type="Symptom", label="p").model_dump()
    with pytest.raises(ValidationError):
        CandidateClaim.model_validate(data)
    data = candidates[0].model_dump()
    data["predicate"] = "PROVES"
    with pytest.raises(ValidationError):
        CandidateClaim.model_validate(data)
    data = candidates[0].model_dump()
    data["extraction_confidence"] = 1.5
    with pytest.raises(ValidationError):
        CandidateClaim.model_validate(data)


# --- conflicts ---------------------------------------------------------------

def conflicting_candidates():
    indicated = extract("Triphala is useful in pandu.", source_id="src-a")[1]
    caution = extract("Triphala is contraindicated in pandu.", source_id="src-b")[1]
    negated = extract("Triphala is not useful in pandu.", source_id="src-c")[1]
    return {c.claim_id: c for c in indicated + caution + negated}


def test_conflicts_are_detected_not_resolved():
    candidates = conflicting_candidates()
    conflicts = attach_conflicts(candidates, detect_conflicts(candidates.values()))

    kinds = sorted(c.kind for c in conflicts.values())
    assert kinds == [ConflictKind.INDICATION_VS_CAUTION, ConflictKind.POLARITY]
    assert all(c.status == ConflictStatus.OPEN for c in conflicts.values())
    assert all(c.conflict_ids for c in candidates.values())
    assert all(c.review_status == ReviewStatus.CANDIDATE for c in candidates.values())


def test_rejected_candidates_do_not_create_conflicts():
    candidates = conflicting_candidates()
    for claim_id, candidate in list(candidates.items()):
        if candidate.predicate == "HAS_CAUTION" or NEGATION_CUE in candidate.uncertainty:
            candidates[claim_id] = candidate.model_copy(
                update={"review_status": ReviewStatus.REJECTED}
            )
    assert detect_conflicts(candidates.values()) == []


# --- review and trust boundary ----------------------------------------------

def one_candidate(text="Pallor is a symptom of pandu."):
    return extract(text)[1][0]


def test_review_requires_reviewer_and_notes():
    candidate = one_candidate()
    with pytest.raises(ReviewError):
        review_candidate(candidate, ReviewStatus.APPROVED, "  ", ReviewerRole.RESEARCHER)
    with pytest.raises(ReviewError):
        review_candidate(candidate, ReviewStatus.REJECTED, "ana", ReviewerRole.RESEARCHER)

    approved, event, _ = review_candidate(
        candidate, ReviewStatus.APPROVED, "ana", ReviewerRole.PRACTITIONER
    )
    assert approved.review_status == ReviewStatus.APPROVED
    assert approved.review_history == [event]
    assert event.from_status == ReviewStatus.CANDIDATE


def test_uncertain_candidates_need_a_note_to_approve():
    caution = by_predicate(extract(
        "Triphala should not be used in pandu.", category=None)[1]
    )[("F-TRIPHALA", "HAS_CAUTION", "R-PANDU")]
    with pytest.raises(ReviewError, match="uncertainty"):
        review_candidate(caution, ReviewStatus.APPROVED, "ana", ReviewerRole.PRACTITIONER)
    approved, _, _ = review_candidate(
        caution, ReviewStatus.APPROVED, "ana", ReviewerRole.PRACTITIONER,
        note="Read in context; the source states a caution.",
    )
    assert approved.review_status == ReviewStatus.APPROVED


def test_transitions_and_history():
    candidate = one_candidate()
    rejected, _, _ = review_candidate(
        candidate, ReviewStatus.REJECTED, "ana", ReviewerRole.RESEARCHER,
        note="Misread sentence.",
    )
    assert rejected.passage == candidate.passage  # passage kept
    with pytest.raises(ReviewError):
        review_candidate(rejected, ReviewStatus.APPROVED, "ana", ReviewerRole.RESEARCHER)
    reopened, _, _ = review_candidate(
        rejected, ReviewStatus.NEEDS_MORE_SOURCES, "ben", ReviewerRole.PRACTITIONER,
        note="Check the commentary.", additional_source_ids=["src-comm"],
    )
    assert [e.to_status for e in reopened.review_history] == [
        ReviewStatus.REJECTED, ReviewStatus.NEEDS_MORE_SOURCES
    ]
    assert reopened.review_history[-1].additional_source_ids == ["src-comm"]


def test_superseding_needs_known_replacement():
    candidate = one_candidate()
    with pytest.raises(ReviewError):
        review_candidate(candidate, ReviewStatus.SUPERSEDED, "ana",
                         ReviewerRole.RESEARCHER, note="better translation")
    with pytest.raises(ReviewError):
        review_candidate(candidate, ReviewStatus.SUPERSEDED, "ana",
                         ReviewerRole.RESEARCHER, note="x", superseded_by="cand-x",
                         known_claim_ids={candidate.claim_id})
    done, _, _ = review_candidate(
        candidate, ReviewStatus.SUPERSEDED, "ana", ReviewerRole.RESEARCHER,
        note="x", superseded_by="cand-x", known_claim_ids={candidate.claim_id, "cand-x"},
    )
    with pytest.raises(ReviewError):
        review_candidate(done, ReviewStatus.APPROVED, "ana", ReviewerRole.RESEARCHER)


def test_open_conflicts_block_approval_until_acknowledged():
    candidates = conflicting_candidates()
    conflicts = attach_conflicts(candidates, detect_conflicts(candidates.values()))
    indicated = next(
        c for c in candidates.values()
        if c.predicate == "TRADITIONALLY_INDICATED_FOR" and NEGATION_CUE not in c.uncertainty
    )
    with pytest.raises(ReviewError, match="open conflict"):
        review_candidate(indicated, ReviewStatus.APPROVED, "ana",
                         ReviewerRole.PRACTITIONER, conflicts=conflicts)
    approved, event, updated = review_candidate(
        indicated, ReviewStatus.APPROVED, "ana", ReviewerRole.PRACTITIONER,
        note="Both statements are in the sources; approving the indication text.",
        acknowledge_conflicts=True, conflicts=conflicts,
    )
    assert sorted(event.acknowledged_conflict_ids) == sorted(indicated.conflict_ids)
    assert all(updated[cid].status == ConflictStatus.ACKNOWLEDGED
               for cid in indicated.conflict_ids)
    assert to_ontology_claim(approved, updated) is None  # no direct ontology mapping


def test_stale_candidates_cannot_be_approved_or_trusted():
    stale = one_candidate().model_copy(update={"stale": True})
    with pytest.raises(ReviewError):
        review_candidate(stale, ReviewStatus.APPROVED, "ana", ReviewerRole.PRACTITIONER)
    approved = one_candidate().model_copy(
        update={"review_status": ReviewStatus.APPROVED, "stale": True}
    )
    assert trusted_candidates([approved]) == []


def test_trust_boundary():
    candidate = one_candidate()
    assert trusted_candidates([candidate]) == []
    with pytest.raises(TrustBoundaryError):
        to_ontology_claim(candidate)

    by_practitioner, _, _ = review_candidate(
        candidate, ReviewStatus.APPROVED, "ana", ReviewerRole.PRACTITIONER
    )
    assert trusted_candidates([candidate, by_practitioner]) == [by_practitioner]
    claim = to_ontology_claim(by_practitioner)
    # HAS_SYMPTOM(Roga, Symptom) maps to the ontology's INDICATES(Symptom, Roga).
    assert (claim.subject_id, claim.predicate, claim.object_id) == (
        "S-PALLOR", "INDICATES", "R-PANDU"
    )
    assert claim.verification_status == VerificationStatus.PRACTITIONER_VERIFIED
    assert claim.confidence is None
    assert "Pallor is a symptom of pandu." in claim.statement

    by_researcher, _, _ = review_candidate(
        candidate, ReviewStatus.APPROVED, "ben", ReviewerRole.RESEARCHER
    )
    assert to_ontology_claim(by_researcher).verification_status == (
        VerificationStatus.LITERATURE_SUPPORTED
    )
    disputed = by_researcher.model_copy(update={"conflict_ids": ["conf-x"]})
    assert to_ontology_claim(disputed).verification_status == VerificationStatus.DISPUTED


# --- store -------------------------------------------------------------------

def source(source_id, texts):
    return (source_id, EvidenceCategory.TRADITIONAL_TEXT, chunks_for(texts, source_id))


def test_rerun_keeps_reviews_and_marks_stale_only_for_processed_sources(tmp_path):
    store = CandidateStore(tmp_path / "cand")
    stats = run_extraction(
        [source("src-a", ["Pallor is a symptom of pandu."]),
         source("src-b", ["Punarnava is indicated in pandu."])],
        EXTRACTOR, store,
    )
    assert stats["new"] == 2
    assert (tmp_path / "cand" / "mentions" / "src-a.jsonl").is_file()

    candidates = store.load_candidates()
    claim_a = next(c for c in candidates.values() if c.passage.source_id == "src-a")
    approved, event, conflicts = review_candidate(
        claim_a, ReviewStatus.APPROVED, "ana", ReviewerRole.PRACTITIONER
    )
    candidates[approved.claim_id] = approved
    store.append_review(event)
    store.save(candidates, conflicts)

    stats = run_extraction([source("src-a", ["Pallor is a symptom of pandu."])], EXTRACTOR, store)
    assert stats["kept_with_review_state"] == 1 and stats["new"] == 0
    reloaded = store.load_candidates()
    assert reloaded[claim_a.claim_id].review_status == ReviewStatus.APPROVED
    assert not any(c.stale for c in reloaded.values())  # src-b not processed

    stats = run_extraction([source("src-a", ["Pallor is a sign of kamala."])], EXTRACTOR, store)
    reloaded = store.load_candidates()
    assert reloaded[claim_a.claim_id].stale  # kept, flagged, not deleted
    assert reloaded[claim_a.claim_id].review_status == ReviewStatus.APPROVED
    assert trusted_candidates(reloaded.values()) == []
    log = (tmp_path / "cand" / "review_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1


# --- CLI ---------------------------------------------------------------------

def test_cli_candidate_workflow(tmp_path, capsys):
    book = tmp_path / "book.md"
    book.write_text(
        "# Pandu\n\nPunarnava is indicated in pandu.\n\n"
        "Triphala is contraindicated in pandu. Triphala is useful in pandu.",
        encoding="utf-8",
    )
    out = tmp_path / "extracted"
    write_extraction(process_source(book), out)
    assert main(["chunk", str(out)]) == 0
    store_dir = tmp_path / "cand"

    assert main(["candidates-extract", str(out), "--out", str(store_dir)]) == 0
    assert "new=3" in capsys.readouterr().out

    assert main(["candidates", str(store_dir), "--show-sentence"]) == 0
    listing = capsys.readouterr().out
    assert "TRADITIONALLY_INDICATED_FOR" in listing and "3 of 3" in listing

    assert main(["conflicts", str(store_dir)]) == 0
    assert "indication_vs_caution" in capsys.readouterr().out

    candidates = CandidateStore(store_dir).load_candidates()
    punarnava = next(c for c in candidates.values() if c.subject.concept_id == "H-PUNARNAVA")
    args = ["review", str(store_dir), punarnava.claim_id, "--status", "approved",
            "--reviewer", "ana", "--role", "practitioner"]
    assert main(args) == 1  # evidence category not declared: note required
    assert "REVIEW REFUSED" in capsys.readouterr().out
    assert main(args + ["--note", "Checked against the printed text."]) == 0
    reloaded = CandidateStore(store_dir).load_candidates()[punarnava.claim_id]
    assert reloaded.review_status == ReviewStatus.APPROVED
    log = (store_dir / "review_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(log[0])["reviewer"] == "ana"

    assert main(["candidates", str(tmp_path / "missing")]) == 2


def test_cue_must_be_near_both_concepts_and_lists_are_noted():
    far = "Triphala " + "x " * 60 + "is indicated in pandu."
    assert extract(far)[1] == []

    _, candidates = extract(
        "Punarnava, guduchi, haritaki, amalaki, bibhitaki, and others are useful in pandu."
    )
    from app.knowledge_candidates.models import LIST_CONTEXT
    candidate = by_predicate(candidates)[
        ("H-PUNARNAVA", "TRADITIONALLY_INDICATED_FOR", "R-PANDU")
    ]
    assert LIST_CONTEXT in candidate.uncertainty


# --- extraction accounting ---------------------------------------------------

from app.knowledge_candidates.store import (  # noqa: E402
    ANALYSIS_FIELDS,
    IDENTITY_FIELDS,
    REVIEW_LIFECYCLE_FIELDS,
)

SYMPTOM_TEXT = "Pallor is a symptom of pandu."
CHANGED_TEXT = "Pallor is a sign of kamala."
REVIEW_FIELDS = ("review_status", "review_history", "extracted_at")


def reviewed_store(tmp_path, category=EvidenceCategory.TRADITIONAL_TEXT):
    """A store with one candidate that has a review decision and history."""
    store = CandidateStore(tmp_path / "cand")
    run_extraction(
        [("src-a", category, chunks_for([SYMPTOM_TEXT], "src-a"))], EXTRACTOR, store
    )
    candidates = store.load_candidates()
    (claim_id, candidate), = candidates.items()
    reviewed, event, conflicts = review_candidate(
        candidate, ReviewStatus.NEEDS_MORE_SOURCES, "reviewer-under-test",
        ReviewerRole.RESEARCHER, note="Test-only review decision.",
    )
    candidates[claim_id] = reviewed
    store.append_review(event)
    store.save(candidates, conflicts)
    return store, claim_id, store.load_candidates()[claim_id]


def run_a(store, text, category=EvidenceCategory.TRADITIONAL_TEXT):
    return run_extraction(
        [("src-a", category, chunks_for([text], "src-a"))], EXTRACTOR, store
    )


def assert_review_unchanged(before, after):
    assert after.claim_id == before.claim_id
    for field in REVIEW_FIELDS:
        assert getattr(after, field) == getattr(before, field), field


def test_field_groups_cover_every_candidate_field_once():
    groups = [IDENTITY_FIELDS, ANALYSIS_FIELDS, REVIEW_LIFECYCLE_FIELDS]
    assert set().union(*groups) == set(CandidateClaim.model_fields)
    assert sum(len(group) for group in groups) == len(CandidateClaim.model_fields)


def test_rerun_with_unchanged_input_is_idempotent(tmp_path):
    store, _, _ = reviewed_store(tmp_path)
    candidates_file = store.candidates_path.read_bytes()
    conflicts_file = store.conflicts_path.read_bytes()

    stats = run_a(store, SYMPTOM_TEXT)

    assert stats["new"] == 0
    assert stats["kept_with_review_state"] == 1
    for counter in ("refreshed_analysis", "revived", "newly_stale", "still_stale"):
        assert stats[counter] == 0, counter
    assert store.candidates_path.read_bytes() == candidates_file
    assert store.conflicts_path.read_bytes() == conflicts_file


def test_stale_transitions_are_counted_once(tmp_path):
    store, claim_id, before = reviewed_store(tmp_path)

    first = run_a(store, CHANGED_TEXT)
    assert (first["newly_stale"], first["still_stale"]) == (1, 0)
    stale = store.load_candidates()[claim_id]
    assert stale.stale is True
    assert_review_unchanged(before, stale)

    second = run_a(store, CHANGED_TEXT)
    assert (second["newly_stale"], second["still_stale"]) == (0, 1)
    assert second["revived"] == 0
    assert_review_unchanged(before, store.load_candidates()[claim_id])


def test_stale_candidate_produced_again_is_revived(tmp_path):
    store, claim_id, before = reviewed_store(tmp_path)
    run_a(store, CHANGED_TEXT)

    stats = run_a(store, SYMPTOM_TEXT)

    assert stats["revived"] == 1
    assert stats["refreshed_analysis"] == 0  # same passage, same analysis
    assert (stats["newly_stale"], stats["still_stale"]) == (0, 0)
    revived = store.load_candidates()[claim_id]
    assert revived.stale is False
    assert_review_unchanged(before, revived)


def test_category_only_change_refreshes_analysis(tmp_path):
    store, claim_id, before = reviewed_store(tmp_path, category=None)
    assert before.evidence_category is None
    assert EVIDENCE_CATEGORY_UNKNOWN in before.uncertainty

    stats = run_a(store, SYMPTOM_TEXT, category=EvidenceCategory.TRADITIONAL_TEXT)

    assert stats["refreshed_analysis"] == 1
    after = store.load_candidates()[claim_id]
    assert after.evidence_category == EvidenceCategory.TRADITIONAL_TEXT
    assert EVIDENCE_CATEGORY_UNKNOWN not in after.uncertainty
    assert after.passage == before.passage
    assert_review_unchanged(before, after)


def test_unprocessed_sources_are_left_exactly_as_stored(tmp_path):
    store, claim_id, before = reviewed_store(tmp_path)

    stats = run_extraction(
        [source("src-b", ["Punarnava is indicated in pandu."])], EXTRACTOR, store
    )

    assert stats["sources"] == 1
    assert (stats["newly_stale"], stats["still_stale"], stats["revived"]) == (0, 0, 0)
    assert store.load_candidates()[claim_id] == before
