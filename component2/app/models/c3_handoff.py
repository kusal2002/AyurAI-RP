"""Component 2 -> Component 3 handoff contract (`c2-to-c3/0.1.0`).

The fields follow the format agreed with the Component 3 owner: upstream
risk metadata, a short Ayurvedic interpretation, and medicinal candidates
(herbs and formulations only, FR12) with display and botanical names,
rank, score, a claim-level rationale and evidence IDs.

Component 2 never invents clinical detail: `dose` is always null (Component 2
does not prescribe; doses quoted in classical texts are not recommendations),
and `botanical_name` is only the name stated by a cited translation.
Component 3 owns patient-specific safety assessment; nothing here states
that a candidate is safe.
"""

from pydantic import BaseModel, Field

from app.models.c1_input import RiskTier
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
MEDICINAL_CATEGORIES = {CandidateCategory.HERB, CandidateCategory.FORMULATION}
PROVISIONAL_LABEL = "Unverified — practitioner review pending"


class UpstreamSummary(BaseModel):
    risk_tier: RiskTier
    calibrated_confidence: float | None
    urgent_clinician_review: bool = False


class RationaleItem(BaseModel):
    claim_id: str
    text: str
    knowledge_status: str = "approved"


class Component3Candidate(BaseModel):
    candidate_id: str
    category: CandidateCategory
    display_name: str | None
    botanical_name: str | None = None
    dose: str | None = Field(
        default=None,
        description="Always null: Component 2 does not prescribe doses.",
    )
    experimental_rank: int
    experimental_ranking_score: float
    disposition: CandidateDisposition
    rationale: list[RationaleItem]
    claim_ids: list[str]
    evidence_ids: list[str]
    knowledge_status: str = Field(
        description="approved, or provisional when any supporting claim is unverified.",
    )
    knowledge_label: str | None = None
    verification_statuses: list[str]
    sufficiency_status: SufficiencyStatus
    uncertainty_flags: list[str]
    conflict_flags: list[str]
    review_required: bool
    # Full provenance, kept for traceability.
    claim_path: list[CandidatePath]
    supporting_evidence: list[EvidenceReference]
    contradicting_evidence: list[EvidenceReference]
    explanation: list[ExplanationStatement]


class Component3Handoff(BaseModel):
    request_id: str
    handoff_schema_version: str = HANDOFF_SCHEMA_VERSION
    source_schema_version: str = OUTPUT_SCHEMA_VERSION
    upstream: UpstreamSummary
    ayurvedic_interpretation: str
    sufficiency_status: SufficiencyStatus
    review_required: bool
    component2_abstained: bool
    abstention_reasons: list[str]
    safety_assessment_performed_by_component2: bool = False
    limitations: list[str]
    candidates: list[Component3Candidate]
    non_medicinal_candidate_ids: list[str] = Field(
        default_factory=list,
        description="Diet and lifestyle candidates, which are not sent for drug-interaction checks.",
    )


def interpretation_text(output: Component2Output) -> str:
    """Pandu / Dosha / Dhatu summary built from the interpreted concepts only."""
    if not output.interpretation:
        return "No Ayurvedic interpretation was reached from the stored claims."
    groups: dict[str, list[str]] = {}
    for concept in output.interpretation:
        groups.setdefault(concept.concept_type, []).append(concept.name or concept.concept_id)
    order = (("Roga", "Roga"), ("Dosha", "associated Dosha"), ("Dhatu", "affected Dhatu"),
             ("TherapeuticPrinciple", "therapeutic principles"))
    parts = [f"{label}: {', '.join(groups[key])}" for key, label in order if key in groups]
    provisional = any(
        step.knowledge_status == "provisional"
        for candidate in output.candidates for path in candidate.paths for step in path.claims
    )
    text = "; ".join(parts) + " (knowledge-graph association, not a diagnosis)"
    return f"{PROVISIONAL_LABEL}: {text}" if provisional else text


def build_component3_handoff(
    output: Component2Output, urgent_clinician_review: bool = False
) -> Component3Handoff:
    candidates = []
    non_medicinal = []
    for candidate in output.candidates:
        if candidate.category not in MEDICINAL_CATEGORIES:
            non_medicinal.append(candidate.candidate_id)
            continue
        refs = {
            (ref.relationship, ref.evidence_id): ref
            for path in candidate.paths
            for claim in path.claims
            for ref in claim.supporting_evidence + claim.contradicting_evidence
        }
        claims = {claim.claim_id: claim for path in candidate.paths for claim in path.claims}
        provisional = any(claim.knowledge_status == "provisional" for claim in claims.values())
        candidates.append(
            Component3Candidate(
                candidate_id=candidate.candidate_id,
                category=candidate.category,
                display_name=candidate.name,
                botanical_name=candidate.botanical_name,
                experimental_rank=candidate.rank,
                experimental_ranking_score=candidate.ranking.score,
                disposition=candidate.disposition,
                rationale=[
                    RationaleItem(
                        claim_id=claim.claim_id,
                        text=claim.statement or f"{claim.subject_id} {claim.predicate} {claim.object_id}",
                        knowledge_status=claim.knowledge_status,
                    )
                    for claim in claims.values()
                ],
                claim_ids=candidate.claim_ids,
                evidence_ids=sorted(
                    set(candidate.supporting_evidence_ids)
                    | set(candidate.contradicting_evidence_ids)
                ),
                knowledge_status="provisional" if provisional else "approved",
                knowledge_label=PROVISIONAL_LABEL if provisional else None,
                verification_statuses=candidate.verification_statuses,
                sufficiency_status=candidate.sufficiency.status,
                uncertainty_flags=candidate.sufficiency.uncertainty_flags,
                conflict_flags=candidate.conflict_flags,
                review_required=candidate.sufficiency.review_required,
                claim_path=candidate.paths,
                supporting_evidence=[
                    ref for (rel, _), ref in sorted(refs.items()) if rel == "SUPPORTS"
                ],
                contradicting_evidence=[
                    ref for (rel, _), ref in sorted(refs.items()) if rel == "CONTRADICTS"
                ],
                explanation=candidate.rationale,
            )
        )

    return Component3Handoff(
        request_id=output.request_id,
        upstream=UpstreamSummary(
            risk_tier=output.upstream.risk_tier,
            calibrated_confidence=output.upstream.calibrated_confidence,
            urgent_clinician_review=urgent_clinician_review,
        ),
        ayurvedic_interpretation=interpretation_text(output),
        sufficiency_status=output.sufficiency_status,
        review_required=output.review_required or urgent_clinician_review,
        component2_abstained=output.abstention.abstain,
        abstention_reasons=output.abstention.reasons,
        limitations=output.limitations,
        candidates=candidates,
        non_medicinal_candidate_ids=non_medicinal,
    )
