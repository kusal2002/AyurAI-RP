"""Provisional evidence-sufficiency, uncertainty and abstention policy.

These rules decide whether a candidate is ready to be forwarded for
downstream safety assessment and practitioner review. They are a
configurable PROTOTYPE pending qualified review; they are not clinical
thresholds and they never express clinical confidence.

Per path, every claim must:
  - have at least `min_supporting_sources` independent supporting sources;
  - have no contradicting evidence and not be `disputed`;
  - have a verification status in `accepted_statuses`;
  - have complete provenance on its supporting evidence (if required);
  - have its statement semantically matched by its own supporting
    evidence at or above the retrieval threshold (if required).

Candidate status:
  - conflicting_evidence if ANY path contains contradiction or a disputed
    claim (conflicts are never outvoted by other paths);
  - otherwise sufficient_for_review if at least one path passes;
  - otherwise unverified_claims if a path fails only on verification;
  - otherwise insufficient_evidence.
"""

from dataclasses import dataclass, field

from app.models.c2_output import (
    CandidatePath,
    SufficiencyAssessment,
    SufficiencyStatus,
)
from app.reasoning.ranking import independent_source_count


@dataclass(frozen=True)
class SufficiencyPolicy:
    policy_id: str = "prototype-sufficiency-v0.1-provisional"
    min_supporting_sources: int = 1
    accepted_statuses: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"literature_supported", "practitioner_verified"}
        )
    )
    require_complete_provenance: bool = True
    require_semantic_retrieval_support: bool = True


def _assess_path(
    path: CandidatePath,
    policy: SufficiencyPolicy,
    retrieval_available: bool,
    min_similarity: float,
) -> tuple[str, set[str], set[str], bool]:
    """Return (state, flags, gaps, conflict) for one path.

    state is "acceptable", "unverified_only" or "insufficient".
    """
    flags: set[str] = set()
    gaps: set[str] = set()
    conflict = False
    insufficient = False
    unverified = False

    for claim in path.claims:
        cid = claim.claim_id

        if claim.evidence_lookup_failed:
            insufficient = True
            gaps.add(f"evidence_lookup_failed:{cid}")

        supporting = independent_source_count(claim.supporting_evidence)
        if supporting == 0:
            insufficient = True
            flags.add("claim_without_supporting_evidence")
            gaps.add(f"no_supporting_evidence:{cid}")
        elif supporting < policy.min_supporting_sources:
            insufficient = True
            gaps.add(f"too_few_independent_sources:{cid}")

        if claim.contradicting_evidence:
            conflict = True
            flags.add(
                "supporting_and_contradicting_evidence"
                if claim.supporting_evidence
                else "contradicting_evidence_only"
            )

        if claim.verification_status == "disputed":
            conflict = True
            flags.add("disputed_claim")
        elif claim.verification_status not in policy.accepted_statuses:
            unverified = True
            flags.add(f"{claim.verification_status}_claim")

        incomplete = [
            ref.evidence_id
            for ref in claim.supporting_evidence
            if not ref.provenance_complete
        ]
        if incomplete:
            flags.add("incomplete_provenance")
            for evidence_id in incomplete:
                gaps.add(f"incomplete_provenance:{evidence_id}")
            if policy.require_complete_provenance:
                insufficient = True

        if policy.require_semantic_retrieval_support and supporting:
            if not retrieval_available:
                insufficient = True
                flags.add("semantic_retrieval_unavailable")
            elif claim.retrieval_similarity is None:
                insufficient = True
                flags.add("semantic_retrieval_not_assessed")
                gaps.add(f"retrieval_not_assessed:{cid}")
            elif claim.retrieval_similarity < min_similarity:
                insufficient = True
                flags.add("retrieval_below_threshold")
                gaps.add(f"retrieval_below_threshold:{cid}")

    if insufficient:
        state = "insufficient"
    elif unverified:
        state = "unverified_only"
    else:
        state = "acceptable"

    return state, flags, gaps, conflict


def assess_candidate(
    paths: list[CandidatePath],
    policy: SufficiencyPolicy,
    retrieval_available: bool,
    min_similarity: float,
) -> SufficiencyAssessment:
    flags: set[str] = set()
    gaps: set[str] = set()
    states = []
    conflicts = []

    for path in paths:
        state, path_flags, path_gaps, conflict = _assess_path(
            path, policy, retrieval_available, min_similarity
        )
        states.append(state)
        conflicts.append(conflict)
        flags |= path_flags
        gaps |= path_gaps

    if len(paths) > 1:
        flags.add("multiple_paths")
        if any(conflicts) and not all(conflicts):
            flags.add("paths_disagree")
        if "acceptable" in states and len(set(states)) > 1:
            flags.add("some_paths_not_sufficient")

    if any(conflicts):
        status = SufficiencyStatus.CONFLICTING_EVIDENCE
    elif "acceptable" in states:
        status = SufficiencyStatus.SUFFICIENT_FOR_REVIEW
    elif "unverified_only" in states:
        status = SufficiencyStatus.UNVERIFIED_CLAIMS
    else:
        status = SufficiencyStatus.INSUFFICIENT_EVIDENCE

    return SufficiencyAssessment(
        status=status,
        review_required=(
            status != SufficiencyStatus.SUFFICIENT_FOR_REVIEW or bool(flags)
        ),
        uncertainty_flags=sorted(flags),
        evidence_gaps=sorted(gaps),
        policy_id=policy.policy_id,
    )


_STATUS_SEVERITY = [
    SufficiencyStatus.CONFLICTING_EVIDENCE,
    SufficiencyStatus.UNVERIFIED_CLAIMS,
    SufficiencyStatus.INSUFFICIENT_EVIDENCE,
]


def assess_request(
    mapped_symptom_count: int,
    candidate_statuses: list[SufficiencyStatus],
) -> tuple[SufficiencyStatus, list[str]]:
    """Return the request-level status and machine-readable abstention
    reasons (empty when Component 2 does not abstain)."""
    if mapped_symptom_count == 0:
        return SufficiencyStatus.OUT_OF_SCOPE, [
            "no_supplied_symptom_mapped_to_stored_concept"
        ]

    if not candidate_statuses:
        return SufficiencyStatus.INSUFFICIENT_EVIDENCE, [
            "no_valid_candidate_path_found"
        ]

    if SufficiencyStatus.SUFFICIENT_FOR_REVIEW in candidate_statuses:
        return SufficiencyStatus.SUFFICIENT_FOR_REVIEW, []

    for status in _STATUS_SEVERITY:
        if status in candidate_statuses:
            return status, [
                "no_candidate_sufficient_for_review",
                f"dominant_candidate_status:{status.value}",
            ]

    return SufficiencyStatus.INSUFFICIENT_EVIDENCE, [
        "no_candidate_sufficient_for_review"
    ]
