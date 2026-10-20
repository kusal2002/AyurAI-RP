import pytest

from app.models.c2_output import (
    CandidatePath,
    ClaimStep,
    EvidenceReference,
    SufficiencyStatus,
)
from app.reasoning.ranking import (
    RankingPolicy,
    independent_source_count,
    rank_candidate,
    score_path,
)
from app.reasoning.sufficiency import (
    SufficiencyPolicy,
    assess_candidate,
    assess_request,
)


def ref(evidence_id, relationship="SUPPORTS", complete=True, source=None):
    return EvidenceReference(
        evidence_id=evidence_id,
        relationship=relationship,
        title=f"T {evidence_id}",
        source_name=source or f"S {evidence_id}",
        evidence_type="classical",
        citation=f"C {evidence_id}",
        provenance_complete=complete,
        missing_provenance=[] if complete else ["title"],
    )


def step(
    claim_id="CL-1",
    status="literature_supported",
    supports=("EV-1",),
    contradicts=(),
    similarity=0.8,
    complete=True,
):
    return ClaimStep(
        claim_id=claim_id,
        subject_id="A",
        subject_type="TherapeuticPrinciple",
        predicate="USES_HERB",
        object_id="H",
        object_type="Herb",
        statement="synthetic statement",
        verification_status=status,
        supporting_evidence=[ref(e, complete=complete) for e in supports],
        contradicting_evidence=[ref(e, "CONTRADICTS") for e in contradicts],
        retrieval_similarity=similarity,
    )


def path(*steps):
    return CandidatePath(
        concept_ids=["X"] * (len(steps) + 1), claims=list(steps)
    )


def assess(paths, retrieval_available=True, policy=None):
    return assess_candidate(
        paths, policy or SufficiencyPolicy(), retrieval_available, 0.3
    )


# Ranking -------------------------------------------------------------------

def test_score_components_are_reported_separately():
    components = score_path(path(step()), RankingPolicy())

    assert components == {
        "status": pytest.approx(0.28),
        "support": pytest.approx(0.1),
        "contradiction": 0.0,
        "provenance": 0.0,
        "retrieval": pytest.approx(0.16),
    }


def test_status_component_orders_statuses():
    policy = RankingPolicy()
    scores = {
        status: score_path(path(step(status=status)), policy)["status"]
        for status in (
            "practitioner_verified",
            "literature_supported",
            "unverified",
            "disputed",
        )
    }
    assert (
        scores["practitioner_verified"]
        > scores["literature_supported"]
        > scores["unverified"]
        > scores["disputed"]
    )


def test_contradiction_lowers_score_without_hiding_it():
    policy = RankingPolicy()
    plain = rank_candidate([path(step())], policy)
    conflicted = rank_candidate(
        [path(step(contradicts=["EV-X"]))], policy
    )

    assert conflicted.components["contradiction"] < 0
    assert conflicted.score < plain.score


def test_independent_sources_merge_same_source():
    refs = [
        ref("EV-1", source="Same"),
        ref("EV-2", source="Same"),
    ]
    refs[1].citation = refs[0].citation

    assert independent_source_count(refs) == 1


def test_support_component_capped():
    policy = RankingPolicy()
    many = score_path(
        path(step(supports=[f"EV-{i}" for i in range(10)])), policy
    )

    assert many["support"] == pytest.approx(policy.w_support)


def test_missing_retrieval_contributes_zero():
    components = score_path(path(step(similarity=None)), RankingPolicy())

    assert components["retrieval"] == 0.0


def test_incomplete_provenance_penalized():
    components = score_path(path(step(complete=False)), RankingPolicy())

    assert components["provenance"] < 0


def test_weakest_claim_limits_path_and_best_path_wins():
    policy = RankingPolicy()
    weak = path(step("CL-A"), step("CL-B", status="unverified"))
    strong = path(step("CL-C"))
    ranking = rank_candidate([weak, strong], policy)

    assert ranking.score == pytest.approx(
        sum(score_path(strong, policy).values())
    )
    assert ranking.label == "experimental_ranking_score_not_clinical_confidence"


def test_ranking_is_deterministic():
    paths = [path(step("CL-A")), path(step("CL-B"))]

    assert rank_candidate(paths, RankingPolicy()) == rank_candidate(
        list(reversed(paths)), RankingPolicy()
    )


# Sufficiency ---------------------------------------------------------------

def test_sufficient_for_review():
    result = assess([path(step())])

    assert result.status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW
    assert result.review_required is False


def test_empty_evidence_is_insufficient():
    result = assess([path(step(supports=()))])

    assert result.status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
    assert "no_supporting_evidence:CL-1" in result.evidence_gaps
    assert result.review_required


def test_insufficient_source_metadata():
    result = assess([path(step(complete=False))])

    assert result.status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
    assert "incomplete_provenance" in result.uncertainty_flags


def test_conflicting_evidence():
    result = assess([path(step(contradicts=["EV-X"]))])

    assert result.status == SufficiencyStatus.CONFLICTING_EVIDENCE
    assert "supporting_and_contradicting_evidence" in result.uncertainty_flags


def test_disputed_claim_is_conflicting():
    result = assess([path(step(status="disputed"))])

    assert result.status == SufficiencyStatus.CONFLICTING_EVIDENCE
    assert "disputed_claim" in result.uncertainty_flags


def test_unverified_claims():
    result = assess([path(step(status="unverified"))])

    assert result.status == SufficiencyStatus.UNVERIFIED_CLAIMS
    assert "unverified_claim" in result.uncertainty_flags


def test_retrieval_threshold_not_met():
    result = assess([path(step(similarity=0.1))])

    assert result.status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
    assert "retrieval_below_threshold" in result.uncertainty_flags


def test_retrieval_unavailable_blocks_sufficiency_by_default():
    result = assess([path(step())], retrieval_available=False)

    assert result.status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
    assert "semantic_retrieval_unavailable" in result.uncertainty_flags


def test_retrieval_requirement_is_configurable():
    policy = SufficiencyPolicy(require_semantic_retrieval_support=False)
    result = assess([path(step())], retrieval_available=False, policy=policy)

    assert result.status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW


def test_conflict_in_one_path_is_not_outvoted():
    result = assess(
        [path(step("CL-A")), path(step("CL-B", contradicts=["EV-X"]))]
    )

    assert result.status == SufficiencyStatus.CONFLICTING_EVIDENCE
    assert "paths_disagree" in result.uncertainty_flags


def test_request_out_of_scope_when_no_symptom_mapped():
    status, reasons = assess_request(0, [])

    assert status == SufficiencyStatus.OUT_OF_SCOPE
    assert reasons == ["no_supplied_symptom_mapped_to_stored_concept"]


def test_request_abstains_without_candidates():
    status, reasons = assess_request(1, [])

    assert status == SufficiencyStatus.INSUFFICIENT_EVIDENCE
    assert reasons == ["no_valid_candidate_path_found"]


def test_request_reports_dominant_failure():
    status, reasons = assess_request(
        1,
        [
            SufficiencyStatus.INSUFFICIENT_EVIDENCE,
            SufficiencyStatus.CONFLICTING_EVIDENCE,
        ],
    )

    assert status == SufficiencyStatus.CONFLICTING_EVIDENCE
    assert "no_candidate_sufficient_for_review" in reasons


def test_request_sufficient_when_one_candidate_sufficient():
    status, reasons = assess_request(
        1,
        [
            SufficiencyStatus.SUFFICIENT_FOR_REVIEW,
            SufficiencyStatus.CONFLICTING_EVIDENCE,
        ],
    )

    assert status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW
    assert reasons == []

def test_ranking_handles_equal_scores_with_same_claim_ids():
    policy = RankingPolicy()

    literature_path = path(
        step(
            "CL-SAME",
            status="literature_supported",
            similarity=0.8,
        )
    )
    practitioner_path = path(
        step(
            "CL-SAME",
            status="practitioner_verified",
            similarity=0.2,
        )
    )

    # Both paths should have equal total scores, despite
    # having different individual score components.
    literature_score = sum(score_path(literature_path, policy).values())
    practitioner_score = sum(score_path(practitioner_path, policy).values())

    assert literature_score == pytest.approx(practitioner_score)

    # Ranking should not crash or depend on input order.
    result_a = rank_candidate(
        [literature_path, practitioner_path], policy
    )
    result_b = rank_candidate(
        [practitioner_path, literature_path], policy
    )

    assert result_a == result_b