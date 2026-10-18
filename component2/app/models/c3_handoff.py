"""Component 2 -> Component 3 handoff contract.

No Component 3 API exists in this repository, so this module defines the
payload Component 2 provides and a pure projection from Component2Output.
Component 3 owns patient-specific safety assessment; nothing here states
that a candidate is safe.
"""

from pydantic import BaseModel

from app.models.c2_output import (
    CandidateCategory,
    CandidateDisposition,
    CandidatePath,
    Component2Output,
    EvidenceReference,
    ExplanationStatement,
    OUTPUT_SCHEMA_VERSION,
    SufficiencyStatus,
)


HANDOFF_SCHEMA_VERSION = "c2-to-c3/0.1.0"


class Component3Candidate(BaseModel):
    candidate_id: str
    category: CandidateCategory
    display_name: str | None
    experimental_rank: int
    experimental_ranking_score: float
    disposition: CandidateDisposition
    claim_path: list[CandidatePath]
    claim_ids: list[str]
    evidence_ids: list[str]
    supporting_evidence: list[EvidenceReference]
    contradicting_evidence: list[EvidenceReference]
    verification_statuses: list[str]
    sufficiency_status: SufficiencyStatus
    uncertainty_flags: list[str]
    conflict_flags: list[str]
    review_required: bool
    rationale: list[ExplanationStatement]


class Component3Handoff(BaseModel):
    handoff_schema_version: str = HANDOFF_SCHEMA_VERSION
    source_schema_version: str = OUTPUT_SCHEMA_VERSION
    request_id: str
    component2_abstained: bool
    abstention_reasons: list[str]
    sufficiency_status: SufficiencyStatus
    review_required: bool
    candidates: list[Component3Candidate]
    limitations: list[str]
    safety_assessment_performed_by_component2: bool = False


def build_component3_handoff(output: Component2Output) -> Component3Handoff:
    candidates = []
    for candidate in output.candidates:
        refs = {
            (ref.relationship, ref.evidence_id): ref
            for path in candidate.paths
            for claim in path.claims
            for ref in claim.supporting_evidence + claim.contradicting_evidence
        }
        candidates.append(
            Component3Candidate(
                candidate_id=candidate.candidate_id,
                category=candidate.category,
                display_name=candidate.name,
                experimental_rank=candidate.rank,
                experimental_ranking_score=candidate.ranking.score,
                disposition=candidate.disposition,
                claim_path=candidate.paths,
                claim_ids=candidate.claim_ids,
                evidence_ids=sorted(
                    set(candidate.supporting_evidence_ids)
                    | set(candidate.contradicting_evidence_ids)
                ),
                supporting_evidence=[
                    ref for (rel, _), ref in sorted(refs.items())
                    if rel == "SUPPORTS"
                ],
                contradicting_evidence=[
                    ref for (rel, _), ref in sorted(refs.items())
                    if rel == "CONTRADICTS"
                ],
                verification_statuses=candidate.verification_statuses,
                sufficiency_status=candidate.sufficiency.status,
                uncertainty_flags=candidate.sufficiency.uncertainty_flags,
                conflict_flags=candidate.conflict_flags,
                review_required=candidate.sufficiency.review_required,
                rationale=candidate.rationale,
            )
        )

    return Component3Handoff(
        request_id=output.request_id,
        component2_abstained=output.abstention.abstain,
        abstention_reasons=output.abstention.reasons,
        sufficiency_status=output.sufficiency_status,
        review_required=output.review_required,
        candidates=candidates,
        limitations=output.limitations,
    )
