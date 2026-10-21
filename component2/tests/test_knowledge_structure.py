"""Regression tests for list co-occurrence vs stated relations.

The sentences reproduce the structure of three passages found in the
corpus (Khare line 10079, Khare lines 10445-10449, Ashtanga Hridaya lines
35572-35575). They are written for these tests and are not verbatim copies
of the source texts.
"""

import hashlib
import json

import pytest

from app.config import IngestionSettings
from app.db.source_repository import plan_promotions, plan_retractions
from app.knowledge_candidates.extractor import (
    EXTRACTOR_NAME,
    EXTRACTOR_VERSION,
    LexiconCueExtractor,
    make_claim_id,
)
from app.knowledge_candidates.lexicon import Lexicon, LexiconMatcher
from app.knowledge_candidates.models import (
    LIST_CONTEXT,
    STRUCTURE_UNSUPPORTED,
    ReviewerRole,
    ReviewEvent,
    ReviewStatus,
)
from app.knowledge_candidates.review import (
    ReviewError,
    review_candidate,
    to_ontology_claim,
    trusted_candidates,
)
from app.knowledge_candidates.store import CandidateStore, run_extraction
from app.knowledge_candidates.structure import (
    CUE_GOVERNS_ENUMERATION,
    SAME_LIST_ITEM,
    SINGLE_CLAUSE,
    assess,
    list_item_spans,
)
from app.knowledge_ingestion.chunking import chunk_passages
from app.knowledge_ingestion.models import (
    EvidenceCategory,
    ExtractedPassage,
    PassageKind,
    SourceLocation,
)


LEXICON = Lexicon.model_validate({
    "lexicon_version": "test-structure", "review_status": "test", "concepts": [
        {"concept_id": "R-PANDU", "concept_type": "Roga", "label": "Pandu",
         "terms": ["pandu"]},
        {"concept_id": "S-FATIGUE", "concept_type": "Symptom", "label": "fatigue",
         "terms": ["fatigue"]},
        {"concept_id": "S-PALLOR", "concept_type": "Symptom", "label": "pallor",
         "terms": ["pallor"]},
        {"concept_id": "DO-VATA", "concept_type": "Dosha", "label": "Vata",
         "terms": ["vata"]},
        {"concept_id": "DO-KAPHA", "concept_type": "Dosha", "label": "Kapha",
         "terms": ["kapha"]},
        {"concept_id": "DO-PITTA", "concept_type": "Dosha", "label": "Pitta",
         "terms": ["pitta"]},
        {"concept_id": "H-HARITAKI", "concept_type": "Herb", "label": "Haritaki",
         "terms": ["haritaki"]},
        {"concept_id": "H-BIBHITAKI", "concept_type": "Herb", "label": "Bibhitaki",
         "terms": ["vibhitaki", "bibhitaki"]},
        {"concept_id": "H-AMALAKI", "concept_type": "Herb", "label": "Amalaki",
         "terms": ["aamalaki", "amalaki"]},
        {"concept_id": "F-TRIPHALA", "concept_type": "Formulation", "label": "Triphala",
         "terms": ["triphala"]},
    ]})
EXTRACTOR = LexiconCueExtractor(LexiconMatcher(LEXICON))

# Structure of Khare line 10079: a cue in the subject's clause governs an
# enumeration of ingredients.
TRIPHALA_COMPOSITION = (
    "In an early period Triphala was composed of one part of Haritaki "
    "(Terminalia chebula), two parts of Vibhitaki (Terminalia bellerica), "
    "and four parts of Aamalaki (Emblica officinalis)."
)
# Structure of Khare lines 10445-10449: a catalogue of drug groups, each
# with its own gloss; Triphala and 'curative of fatigue' sit in different
# entries.
DRUG_GROUP_CATALOGUE = (
    "Group of a classical author: Virechanopaga (purgative, due to Triphala), "
    "shramahara (curative of fatigue), hridya (cordial), "
    "trishnanigrahana (curative of morbid thirst)."
)
# Structure of Ashtanga Hridaya lines 35572-35575: a bare list of actions
# and indications; dosha names and 'pandu' are separate entries.
INDICATION_LIST = (
    "Dipana, kapha vata hara, sopha, udara, arsas, grahani dosa, "
    "mutragraha, aruci, pliha, gulma, garavisa, pandu"
)


def chunk_for(text, source_id="src-structure"):
    passage = ExtractedPassage(
        passage_index=0, kind=PassageKind.PARAGRAPH, text=text,
        location=SourceLocation(block_index=0, line_start=1, line_end=1),
    )
    return chunk_passages(
        source_id, [passage],
        IngestionSettings(chunk_max_chars=800, chunk_overlap_chars=0),
    )[0]


def extract(text):
    return EXTRACTOR.extract(chunk_for(text), EvidenceCategory.TRADITIONAL_TEXT)[1]


def relations(candidates):
    return {
        (c.subject.concept_id, c.predicate, c.object.concept_id): c
        for c in candidates
    }


# --- list items --------------------------------------------------------------

def test_list_items_ignore_commas_inside_parentheses():
    items = [DRUG_GROUP_CATALOGUE[s:e].strip() for s, e in list_item_spans(DRUG_GROUP_CATALOGUE)]
    assert items[0] == "Group of a classical author: Virechanopaga (purgative, due to Triphala)"
    assert items[1] == "shramahara (curative of fatigue)"
    assert len(items) == 4


def test_assessment_bases():
    sentence = "Pandu is caused by vitiated pitta."
    assert assess(sentence, (0, 5), (28, 33), (9, 18)).basis == SINGLE_CLAUSE
    listed = "Pallor, fatigue are symptoms of pandu"
    # cue 'symptoms' and subject 'pandu' share the last item; objects precede it.
    assert assess(listed, (32, 37), (0, 6), (20, 28)).basis == CUE_GOVERNS_ENUMERATION
    both = "x, pandu is caused by vata, y"
    assert assess(both, (3, 8), (22, 26), (12, 21)).basis == SAME_LIST_ITEM


# --- regression: Khare composition (supported) -------------------------------

def test_khare_composition_yields_all_three_ingredients_without_flag():
    found = relations(extract(TRIPHALA_COMPOSITION))
    for herb in ("H-HARITAKI", "H-BIBHITAKI", "H-AMALAKI"):
        candidate = found[("F-TRIPHALA", "CONTAINS_INGREDIENT", herb)]
        assert STRUCTURE_UNSUPPORTED not in candidate.uncertainty
        assert candidate.cue == "composed of"
    # Herbs are listed together but are not said to contain each other.
    assert all(key[1] == "CONTAINS_INGREDIENT" for key in found)


def test_khare_composition_can_be_approved_and_stays_descriptive():
    found = relations(extract(TRIPHALA_COMPOSITION))
    candidate = found[("F-TRIPHALA", "CONTAINS_INGREDIENT", "H-AMALAKI")]
    approved, _, _ = review_candidate(
        candidate, ReviewStatus.APPROVED, "reviewer-under-test",
        ReviewerRole.PRACTITIONER, note="test-only approval",
    )
    claim = to_ontology_claim(approved)
    assert claim.predicate == "CONTAINS_INGREDIENT"
    from app.ontology.relationships import RELATIONSHIP_RULES
    assert claim.predicate not in RELATIONSHIP_RULES  # never traversed by reasoning


# --- regression: Khare drug-group catalogue (not supported) ------------------

def test_khare_catalogue_fatigue_is_flagged_not_established():
    found = relations(extract(DRUG_GROUP_CATALOGUE))
    fatigue = found[("F-TRIPHALA", "TRADITIONALLY_INDICATED_FOR", "S-FATIGUE")]
    assert STRUCTURE_UNSUPPORTED in fatigue.uncertainty
    with pytest.raises(ReviewError, match="does not establish"):
        review_candidate(fatigue, ReviewStatus.APPROVED, "reviewer-under-test",
                         ReviewerRole.PRACTITIONER, note="x")
    # Rejecting or asking for more sources is still possible.
    rejected, _, _ = review_candidate(
        fatigue, ReviewStatus.REJECTED, "reviewer-under-test",
        ReviewerRole.RESEARCHER, note="List co-occurrence only.",
    )
    assert rejected.passage == fatigue.passage


# --- regression: Ashtanga indication list (not supported) --------------------

def test_ashtanga_list_does_not_relate_pandu_to_doshas():
    found = relations(extract(INDICATION_LIST))
    # 'grahani dosa' is a disease name, not a causal cue (extractor v4).
    assert not any(key[1] == "ASSOCIATED_WITH_DOSHA" for key in found)


def test_list_with_a_real_cue_elsewhere_is_kept_but_flagged():
    # A genuine aggravation cue in an unrelated list item: the pair is still
    # shown for review (not silently dropped) but flagged and unusable.
    sentence = ("Dipana, kapha vata hara, sopha, udara, aggravated grahani, "
                "mutragraha, aruci, pandu")
    found = relations(extract(sentence))
    for dosha in ("DO-VATA", "DO-KAPHA"):
        key = ("R-PANDU", "ASSOCIATED_WITH_DOSHA", dosha)
        assert key in found
        assert STRUCTURE_UNSUPPORTED in found[key].uncertainty
        assert LIST_CONTEXT in found[key].uncertainty
        assert trusted_candidates([found[key]]) == []
        with pytest.raises(ReviewError):
            review_candidate(found[key], ReviewStatus.APPROVED,
                             "reviewer-under-test", ReviewerRole.PRACTITIONER,
                             note="x")


def test_flagged_candidates_are_skipped_by_promotion_even_if_marked_approved():
    # A flagged candidate whose predicate maps to the ontology, so both
    # promotion and retraction planning apply to it.
    found = relations(extract(
        "Dipana, kapha vata hara, sopha, udara, aggravated grahani, "
        "mutragraha, aruci, pandu"
    ))
    flagged = found[("R-PANDU", "ASSOCIATED_WITH_DOSHA", "DO-VATA")]
    assert STRUCTURE_UNSUPPORTED in flagged.uncertainty
    # Simulate an older record that was approved before the check existed.
    event = ReviewEvent(
        claim_id=flagged.claim_id, reviewer="reviewer-under-test",
        reviewer_role=ReviewerRole.PRACTITIONER,
        from_status=ReviewStatus.CANDIDATE, to_status=ReviewStatus.APPROVED,
    )
    legacy = flagged.model_copy(update={
        "review_status": ReviewStatus.APPROVED, "review_history": [event],
    })
    report = plan_promotions([legacy], {}, {}, {})
    assert report.skipped == [
        (legacy.claim_id, "relation not supported by the sentence structure")
    ]
    retraction = plan_retractions([legacy])
    assert retraction.plans[0].retracted_by == "system:structure_check"


# --- controls: real relations are still found --------------------------------

@pytest.mark.parametrize("sentence, expected", [
    ("Pandu is caused by vitiated pitta.", ("R-PANDU", "ASSOCIATED_WITH_DOSHA", "DO-PITTA")),
    ("Pandu is caused by vata, kapha and pitta.", ("R-PANDU", "ASSOCIATED_WITH_DOSHA", "DO-KAPHA")),
    ("Pallor and fatigue are symptoms of pandu.", ("R-PANDU", "HAS_SYMPTOM", "S-FATIGUE")),
])
def test_stated_relations_are_not_flagged(sentence, expected):
    candidate = relations(extract(sentence))[expected]
    assert STRUCTURE_UNSUPPORTED not in candidate.uncertainty


# --- identity and history preservation ---------------------------------------

def test_claim_ids_keep_the_v2_scheme():
    assert EXTRACTOR_VERSION == "4"
    payload = json.dumps(
        [EXTRACTOR_NAME, "2", "src#chk-1", 0, 10, "F-TRIPHALA",
         "CONTAINS_INGREDIENT", "H-HARITAKI"],
        separators=(",", ":"), ensure_ascii=False,
    )
    expected = "cand-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    assert make_claim_id("src#chk-1", 0, 10, "F-TRIPHALA",
                         "CONTAINS_INGREDIENT", "H-HARITAKI") == expected


def test_reextraction_refreshes_flags_but_keeps_review_history(tmp_path):
    store = CandidateStore(tmp_path / "cand")
    chunk = chunk_for(DRUG_GROUP_CATALOGUE, "src-k")
    source = [("src-k", EvidenceCategory.TRADITIONAL_TEXT, [chunk])]
    run_extraction(source, EXTRACTOR, store)
    candidates = store.load_candidates()
    claim_id, fatigue = next(
        (cid, c) for cid, c in candidates.items() if c.object.concept_id == "S-FATIGUE"
    )
    reviewed, event, conflicts = review_candidate(
        fatigue, ReviewStatus.NEEDS_MORE_SOURCES, "reviewer-under-test",
        ReviewerRole.RESEARCHER, note="Check the group attribution.",
    )
    # Pretend an older extractor had not flagged it.
    candidates[claim_id] = reviewed.model_copy(update={
        "uncertainty": [], "extractor_version": "2",
    })
    store.append_review(event)
    store.save(candidates, conflicts)

    stats = run_extraction(source, EXTRACTOR, store)
    after = store.load_candidates()[claim_id]
    assert stats["refreshed_analysis"] >= 1
    assert after.claim_id == claim_id
    assert after.passage.chunk_id == chunk.chunk_id
    assert after.extractor_version == EXTRACTOR_VERSION
    assert STRUCTURE_UNSUPPORTED in after.uncertainty
    assert after.review_status == ReviewStatus.NEEDS_MORE_SOURCES
    assert after.review_history == reviewed.review_history
    assert after.extracted_at == fatigue.extracted_at


# --- audit regressions (structure of the real passages, not verbatim) --------

# Group catalogue whose next heading lacks a full stop, so it fuses with the
# last list item; Triphala reappears only under a synonym in the next group.
VARGA_WITH_NEXT_GROUP = (
    "Group of one author: Virechanopaga (purgative, due to Triphala), "
    "shramahara (curative of fatigue), hridya (cordial), "
    "trishnanigrahana (curative of morbid thirst) Group of another author: "
    "Parushaka, Varaa (Triphala), Draksha, Dadima."
)
# Indication list in which the only dosha-like word is part of a disease name.
LIST_WITH_DISEASE_NAME = (
    "Dipana, kapha vata hara, sopha, udara, grahani dosa, mutragraha, "
    "aruci, pliha, gulma, pandu"
)
# Two periods, two proportions; the second sentence names no concept and
# uses 'used in' only in the sense of proportions.
HISTORICAL_COMPOSITION = (
    "During the period of an early author, Triphala was composed of one part "
    "of Haritaki, two parts of Vibhitaki, and four parts of Aamalaki. "
    "During the period of a later author all the three components were used "
    "in equal parts."
)


def unflagged(candidates, predicate):
    return [
        c for c in candidates
        if c.predicate == predicate and STRUCTURE_UNSUPPORTED not in c.uncertainty
    ]


def test_group_catalogue_never_supports_triphala_fatigue():
    candidates = extract(VARGA_WITH_NEXT_GROUP)
    assert unflagged(candidates, "TRADITIONALLY_INDICATED_FOR") == []
    assert trusted_candidates(candidates) == []


def test_disease_name_containing_dosha_never_supports_a_dosha_relation():
    candidates = extract(LIST_WITH_DISEASE_NAME)
    # Either not produced or flagged; never a usable relation.
    assert unflagged(candidates, "ASSOCIATED_WITH_DOSHA") == []
    for candidate in candidates:
        with pytest.raises(ReviewError):
            review_candidate(candidate, ReviewStatus.APPROVED,
                             "reviewer-under-test", ReviewerRole.PRACTITIONER,
                             note="x")


def test_historical_composition_keeps_its_period_and_stays_descriptive():
    from app.ontology.relationships import RELATIONSHIP_RULES

    candidates = extract(HISTORICAL_COMPOSITION)
    found = relations(candidates)
    assert set(found) == {
        ("F-TRIPHALA", "CONTAINS_INGREDIENT", "H-HARITAKI"),
        ("F-TRIPHALA", "CONTAINS_INGREDIENT", "H-BIBHITAKI"),
        ("F-TRIPHALA", "CONTAINS_INGREDIENT", "H-AMALAKI"),
    }  # nothing is inferred from 'used in equal parts'
    for candidate in found.values():
        assert STRUCTURE_UNSUPPORTED not in candidate.uncertainty
        assert candidate.passage.sentence.startswith("During the period of an early author")
        assert "one part of Haritaki" in candidate.passage.sentence

    approved, _, _ = review_candidate(
        found[("F-TRIPHALA", "CONTAINS_INGREDIENT", "H-AMALAKI")],
        ReviewStatus.APPROVED, "reviewer-under-test", ReviewerRole.RESEARCHER,
        note="test-only approval",
    )
    claim = to_ontology_claim(approved)
    assert claim.predicate not in RELATIONSHIP_RULES
    assert "During the period of an early author" in claim.statement
    assert "four parts of Aamalaki" in claim.statement


# --- extractor v4: dosha cue (P1) and period/proportion qualifier (P2) -------

from app.knowledge_candidates.models import QUALIFIED_STATEMENT  # noqa: E402


@pytest.mark.parametrize("sentence", [
    "Pandu, grahani dosa and vata are listed here.",
    "The dosha of pandu and vata are mentioned together.",
    "पाण्डु दोष वात",
])
def test_bare_dosha_word_is_not_a_relation_cue(sentence):
    lexicon = Lexicon.model_validate({
        "lexicon_version": "t", "review_status": "t", "concepts": [
            {"concept_id": "R-PANDU", "concept_type": "Roga", "label": "Pandu",
             "terms": ["pandu", "पाण्डु"]},
            {"concept_id": "DO-VATA", "concept_type": "Dosha", "label": "Vata",
             "terms": ["vata", "वात"]},
        ]})
    chunk = chunk_for(sentence)
    _, candidates = LexiconCueExtractor(LexiconMatcher(lexicon)).extract(chunk)
    assert [c for c in candidates if c.predicate == "ASSOCIATED_WITH_DOSHA"] == []


@pytest.mark.parametrize("sentence", [
    "Pandu is caused by vitiated pitta.",
    "In pandu, aggravated kapha predominates.",
])
def test_causal_dosha_cues_still_work(sentence):
    found = relations(extract(sentence))
    assert any(key[0] == "R-PANDU" and key[1] == "ASSOCIATED_WITH_DOSHA" for key in found)


def test_period_and_proportion_qualifier_is_noted_but_not_blocking():
    candidates = extract(HISTORICAL_COMPOSITION)
    assert candidates
    for candidate in candidates:
        assert QUALIFIED_STATEMENT in candidate.uncertainty
        assert STRUCTURE_UNSUPPORTED not in candidate.uncertainty
    # Not blocking: a reviewer can approve it (a note is required, as for any
    # candidate with uncertainty notes) and it becomes trusted.
    with pytest.raises(ReviewError, match="needs a note"):
        review_candidate(candidates[0], ReviewStatus.APPROVED,
                         "reviewer-under-test", ReviewerRole.RESEARCHER)
    approved, _, _ = review_candidate(
        candidates[0], ReviewStatus.APPROVED, "reviewer-under-test",
        ReviewerRole.RESEARCHER, note="Applies to the stated period only.",
    )
    assert trusted_candidates([approved]) == [approved]


@pytest.mark.parametrize("sentence", [
    "Triphala was composed of haritaki in equal quantities with other fruits.",
    "In the time of the commentator, Triphala was composed of haritaki.",
    "Triphala, as described in the tenth century, was composed of haritaki.",
])
def test_qualifier_patterns(sentence):
    (candidate,) = extract(sentence)
    assert QUALIFIED_STATEMENT in candidate.uncertainty


def test_unqualified_statement_has_no_qualifier_note():
    (candidate,) = extract("Triphala is composed of haritaki.")
    assert QUALIFIED_STATEMENT not in candidate.uncertainty
