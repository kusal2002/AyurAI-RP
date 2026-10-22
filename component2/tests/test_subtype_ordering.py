"""Roga types (subtype_of): remedies for the patient's matched type come first.

Synthetic source and synthetic drafts only; no live database.
"""

from types import SimpleNamespace

from app.knowledge_provisional.plan import plan_dataset
from app.models.c1_input import Component2ReasoningRequest
from app.models.c2_output import CandidateCategory, CandidateDisposition
from app.reasoning.pipeline import candidate_order_key, run_component2_reasoning
from c2_test_support import make_retrieval_service
from test_provisional_pathway import CONCEPTS, PlanGraph, _claim, _dataset, extracted  # noqa: F401 (fixture)

FORWARD = CandidateDisposition.FORWARD_FOR_SAFETY_ASSESSMENT
WITHHELD = CandidateDisposition.WITHHELD_PENDING_REVIEW


def _row(candidate_id, score, matched=(), disposition=WITHHELD):
    return {"candidate_id": candidate_id, "category": CandidateCategory.HERB, "disposition": disposition,
            "ranking": SimpleNamespace(score=score), "matched_subtypes": list(matched)}


# --- ordering rule --------------------------------------------------------------------

def test_matched_type_comes_before_a_higher_scoring_general_remedy():
    rows = [_row("H-GENERAL", 0.9), _row("H-TYPE", 0.2, matched=["R-PANDU-PITTAJA"])]
    assert [r["candidate_id"] for r in sorted(rows, key=candidate_order_key)] == ["H-TYPE", "H-GENERAL"]


def test_forwarded_candidates_still_come_first():
    # A type match never lifts a withheld candidate above a forwarded one.
    rows = [_row("H-TYPE", 0.9, matched=["R-PANDU-PITTAJA"]), _row("H-FORWARDED", 0.1, disposition=FORWARD)]
    assert [r["candidate_id"] for r in sorted(rows, key=candidate_order_key)] == ["H-FORWARDED", "H-TYPE"]


def test_score_orders_candidates_within_the_same_group():
    rows = [_row("H-A", 0.3, matched=["R-X"]), _row("H-B", 0.8, matched=["R-X"]), _row("H-C", 0.5), _row("H-D", 0.6)]
    assert [r["candidate_id"] for r in sorted(rows, key=candidate_order_key)] == ["H-B", "H-A", "H-D", "H-C"]


# --- planner -----------------------------------------------------------------------

SUBTYPE_CONCEPTS = CONCEPTS + [
    {"type": "Symptom", "id": "S-BURNING", "name": "burning sensation", "aliases": []},
    {"type": "Roga", "id": "R-PANDU-PITTAJA", "name": "Pittaja Pandu", "aliases": [], "subtype_of": "R-PANDU"},
    {"type": "TherapeuticPrinciple", "id": "TP-PITTA", "name": "Bitter and cooling treatment", "aliases": []},
    {"type": "Herb", "id": "H-TRIVRIT", "name": "Trivṛt", "aliases": []},
]

SUBTYPE_CLAIMS = [
    _claim("pallor-pandu", "S-PALLOR", "INDICATES", "R-PANDU"),
    _claim("pandu-tp", "R-PANDU", "SUGGESTS_PRINCIPLE", "TP-SYN",
           quote="pāṇḍuroge lakṣaṇāni vakṣyāmi/", element="Syn.6.16.1"),
    _claim("tp-herb", "TP-SYN", "USES_HERB", "H-PUNARNAVA", quote="triphalā punarnavā ca", element="Syn.6.16.3"),
    _claim("burning-pittaja", "S-BURNING", "INDICATES", "R-PANDU-PITTAJA"),
    _claim("pittaja-tp", "R-PANDU-PITTAJA", "SUGGESTS_PRINCIPLE", "TP-PITTA",
           quote="pāṇḍuroge lakṣaṇāni vakṣyāmi/", element="Syn.6.16.1"),
    _claim("tp-trivrit", "TP-PITTA", "USES_HERB", "H-TRIVRIT", quote="triphalā punarnavā ca", element="Syn.6.16.3"),
]


def test_plan_keeps_subtype_of_for_roga(tmp_path, extracted):  # noqa: F811
    plan = plan_dataset(_dataset(tmp_path, concepts=SUBTYPE_CONCEPTS, claims=SUBTYPE_CLAIMS, refs=[]), extracted)
    assert plan.concepts["R-PANDU-PITTAJA"]["properties"]["subtype_of"] == "R-PANDU"
    assert "subtype_of" not in plan.concepts["R-PANDU"]["properties"]
    assert plan.rejected == []


def test_plan_rejects_subtype_of_that_is_not_a_roga(tmp_path, extracted):  # noqa: F811
    concepts = SUBTYPE_CONCEPTS + [
        {"type": "Roga", "id": "R-ORPHAN", "name": "Orphan type", "aliases": [], "subtype_of": "R-MISSING"},
        {"type": "Roga", "id": "R-WRONG", "name": "Wrong parent", "aliases": [], "subtype_of": "TP-SYN"},
    ]
    plan = plan_dataset(_dataset(tmp_path, concepts=concepts, claims=SUBTYPE_CLAIMS, refs=[]), extracted)
    assert {r["item"] for r in plan.rejected} == {"R-ORPHAN", "R-WRONG"}
    assert "R-ORPHAN" not in plan.concepts and "R-WRONG" not in plan.concepts


def test_subtype_of_is_ignored_on_other_concept_types(tmp_path, extracted):  # noqa: F811
    concepts = [dict(c, subtype_of="R-PANDU") if c["id"] == "H-PUNARNAVA" else c for c in SUBTYPE_CONCEPTS]
    plan = plan_dataset(_dataset(tmp_path, concepts=concepts, claims=SUBTYPE_CLAIMS, refs=[]), extracted)
    assert "subtype_of" not in plan.concepts["H-PUNARNAVA"]["properties"]


# --- reasoning, end to end ------------------------------------------------------------

def _run(plan, symptom_ids):
    graph = PlanGraph(plan)
    request = Component2ReasoningRequest(request_id="req-subtype", risk_tier="moderate",
                                         calibrated_confidence=None, symptom_ids=symptom_ids)
    return run_component2_reasoning(request, retrieval_service=make_retrieval_service(graph), graph=graph)


def test_general_symptoms_reach_only_general_remedies(tmp_path, extracted):  # noqa: F811
    plan = plan_dataset(_dataset(tmp_path, concepts=SUBTYPE_CONCEPTS, claims=SUBTYPE_CLAIMS, refs=[]), extracted)
    output = _run(plan, ["S-PALLOR"])
    assert [c.candidate_id for c in output.candidates] == ["H-PUNARNAVA"]
    assert output.candidates[0].matched_subtypes == []


def test_matched_type_remedy_is_listed_first_with_score_unchanged(tmp_path, extracted):  # noqa: F811
    plan = plan_dataset(_dataset(tmp_path, concepts=SUBTYPE_CONCEPTS, claims=SUBTYPE_CLAIMS, refs=[]), extracted)
    general_only = _run(plan, ["S-PALLOR"])
    output = _run(plan, ["S-PALLOR", "S-BURNING"])

    first, second = output.candidates
    assert (first.candidate_id, first.rank, first.matched_subtypes) == ("H-TRIVRIT", 1, ["R-PANDU-PITTAJA"])
    assert (second.candidate_id, second.rank, second.matched_subtypes) == ("H-PUNARNAVA", 2, [])
    # The general remedy keeps exactly the score it had without the type.
    assert second.ranking.score == general_only.candidates[0].ranking.score
    assert any(s.kind == "subtype_match" for s in first.rationale)
    assert not any(s.kind == "subtype_match" for s in second.rationale)
    assert {c.name for c in output.interpretation if c.concept_type == "Roga"} == {"Pandu", "Pittaja Pandu"}


def test_type_with_no_remedy_is_traced_in_interpretation_claims(tmp_path, extracted):  # noqa: F811
    concepts = SUBTYPE_CONCEPTS + [
        {"type": "Symptom", "id": "S-TREMOR", "name": "tremor", "aliases": []},
        {"type": "Roga", "id": "R-PANDU-VATAJA", "name": "Vātaja Pandu", "aliases": [], "subtype_of": "R-PANDU"},
        {"type": "TherapeuticPrinciple", "id": "TP-VATA", "name": "Unctuous treatment", "aliases": []},
    ]
    claims = SUBTYPE_CLAIMS + [
        _claim("tremor-vataja", "S-TREMOR", "INDICATES", "R-PANDU-VATAJA"),
        _claim("vataja-tp", "R-PANDU-VATAJA", "SUGGESTS_PRINCIPLE", "TP-VATA",
               quote="pāṇḍuroge lakṣaṇāni vakṣyāmi/", element="Syn.6.16.1"),
    ]
    plan = plan_dataset(_dataset(tmp_path, concepts=concepts, claims=claims, refs=[]), extracted)
    output = _run(plan, ["S-PALLOR", "S-TREMOR"])

    # No Vāta-specific remedy: candidates and their order are unchanged.
    assert [c.candidate_id for c in output.candidates] == ["H-PUNARNAVA"]
    traced = {(c.subject_id, c.predicate, c.object_id) for c in output.interpretation_claims}
    assert traced == {
        ("S-TREMOR", "INDICATES", "R-PANDU-VATAJA"),
        ("R-PANDU-VATAJA", "SUGGESTS_PRINCIPLE", "TP-VATA"),
    }
    on_paths = {s.claim_id for c in output.candidates for p in c.paths for s in p.claims}
    assert not on_paths & {c.claim_id for c in output.interpretation_claims}
    assert all(c.supporting_evidence for c in output.interpretation_claims)
    subtype_of = {c.concept_id: c.subtype_of for c in output.interpretation if c.concept_type == "Roga"}
    assert subtype_of == {"R-PANDU": None, "R-PANDU-VATAJA": "R-PANDU"}
