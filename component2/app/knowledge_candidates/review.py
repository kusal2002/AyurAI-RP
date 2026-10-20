"""Review workflow and the trust boundary for candidate claims.

Status changes are explicit, attributed to a named reviewer and appended to
the candidate's history; nothing is deleted, and a rejected candidate keeps
its supporting passage. Approval means "a reviewer confirmed this source
states this", not that the statement is medically true.

Only trusted_candidates() releases candidates beyond review, and only
to_ontology_claim() turns one into a graph Claim. Neither writes to Neo4j.
"""

from typing import Iterable

from app.knowledge_candidates.models import (
    BLOCKING_UNCERTAINTY,
    ONTOLOGY_MAPPING,
    CandidateClaim,
    Conflict,
    ConflictStatus,
    ReviewerRole,
    ReviewEvent,
    ReviewStatus,
)
from app.models.claim import Claim, VerificationStatus
from app.ontology.relationships import validate_relationship


class ReviewError(ValueError):
    """A review action is not allowed in the candidate's current state."""


class TrustBoundaryError(ValueError):
    """A candidate that is not approved was used as trusted knowledge."""


_REVIEWABLE = {
    ReviewStatus.APPROVED,
    ReviewStatus.REJECTED,
    ReviewStatus.UNCERTAIN,
    ReviewStatus.NEEDS_MORE_SOURCES,
    ReviewStatus.SUPERSEDED,
}
ALLOWED_TRANSITIONS = {
    ReviewStatus.CANDIDATE: _REVIEWABLE,
    ReviewStatus.UNCERTAIN: _REVIEWABLE,
    ReviewStatus.NEEDS_MORE_SOURCES: _REVIEWABLE,
    # Withdrawing an approval is allowed and recorded.
    ReviewStatus.APPROVED: {
        ReviewStatus.REJECTED,
        ReviewStatus.UNCERTAIN,
        ReviewStatus.NEEDS_MORE_SOURCES,
        ReviewStatus.SUPERSEDED,
    },
    # A rejected candidate can be reopened, not approved directly.
    ReviewStatus.REJECTED: {ReviewStatus.UNCERTAIN, ReviewStatus.NEEDS_MORE_SOURCES},
    ReviewStatus.SUPERSEDED: set(),
}


def review_candidate(
    candidate: CandidateClaim,
    to_status: ReviewStatus,
    reviewer: str,
    reviewer_role: ReviewerRole,
    note: str | None = None,
    additional_source_ids: Iterable[str] = (),
    superseded_by: str | None = None,
    acknowledge_conflicts: bool = False,
    conflicts: dict[str, Conflict] | None = None,
    known_claim_ids: set[str] | None = None,
) -> tuple[CandidateClaim, ReviewEvent, dict[str, Conflict]]:
    """Apply one review decision. Returns (candidate, event, conflicts).

    Rules:
    * reviewer must be named; every decision except a plain approval needs a
      note, and so does approving a candidate with uncertainty notes;
    * a candidate with open conflicts can be approved only with
      acknowledge_conflicts=True (the conflicts become acknowledged, not
      resolved);
    * stale candidates (passage changed) cannot be approved;
    * superseding needs the ID of an existing replacement candidate.
    """
    reviewer = (reviewer or "").strip()
    note = (note or "").strip() or None
    conflicts = dict(conflicts or {})

    if not reviewer:
        raise ReviewError("A named reviewer is required.")
    if to_status not in ALLOWED_TRANSITIONS[candidate.review_status]:
        raise ReviewError(
            f"Cannot change {candidate.review_status.value} to {to_status.value}."
        )
    if to_status != ReviewStatus.APPROVED and note is None:
        raise ReviewError(f"A note is required to mark a candidate {to_status.value}.")

    acknowledged: list[str] = []
    if to_status == ReviewStatus.APPROVED:
        blocking = sorted(BLOCKING_UNCERTAINTY & set(candidate.uncertainty))
        if blocking:
            raise ReviewError(
                "The supporting sentence does not establish this relation ("
                + ", ".join(blocking)
                + "); it cannot be approved. Reject it, or mark it "
                "needs_more_sources and cite a passage that states it."
            )
        if candidate.stale:
            raise ReviewError(
                "The supporting passage changed or was removed; re-extract "
                "before approving."
            )
        if candidate.uncertainty and note is None:
            raise ReviewError(
                "This candidate has uncertainty notes ("
                + ", ".join(candidate.uncertainty)
                + "); approving it needs a note."
            )
        open_ids = [
            conflict_id for conflict_id in candidate.conflict_ids
            if conflict_id in conflicts
            and conflicts[conflict_id].status == ConflictStatus.OPEN
        ]
        if open_ids and not acknowledge_conflicts:
            raise ReviewError(
                f"Candidate has {len(open_ids)} open conflict(s); review them "
                "and approve with acknowledge_conflicts."
            )
        for conflict_id in open_ids:
            conflict = conflicts[conflict_id]
            conflicts[conflict_id] = conflict.model_copy(
                update={
                    "status": ConflictStatus.ACKNOWLEDGED,
                    "acknowledged_by": sorted({*conflict.acknowledged_by, reviewer}),
                }
            )
            acknowledged.append(conflict_id)

    if to_status == ReviewStatus.SUPERSEDED:
        if not superseded_by or superseded_by == candidate.claim_id:
            raise ReviewError("superseded_by must name another candidate.")
        if known_claim_ids is not None and superseded_by not in known_claim_ids:
            raise ReviewError(f"Unknown replacement candidate {superseded_by!r}.")
    elif superseded_by:
        raise ReviewError("superseded_by is only valid when superseding.")

    event = ReviewEvent(
        claim_id=candidate.claim_id,
        reviewer=reviewer,
        reviewer_role=reviewer_role,
        from_status=candidate.review_status,
        to_status=to_status,
        note=note,
        additional_source_ids=[s for s in additional_source_ids if s.strip()],
        superseded_by=superseded_by,
        acknowledged_conflict_ids=acknowledged,
    )
    updated = candidate.model_copy(
        update={
            "review_status": to_status,
            "review_history": [*candidate.review_history, event],
        }
    )
    return updated, event, conflicts


def approval_event(candidate: CandidateClaim) -> ReviewEvent | None:
    """The review event behind an APPROVED status, or None.

    A status is only trusted when the candidate's latest review event is an
    approval of this candidate by a named reviewer. A status set without
    such an event (for example by editing candidates.jsonl or by
    model_copy) is not an approval.
    """
    if candidate.review_status != ReviewStatus.APPROVED:
        return None
    if not candidate.review_history:
        return None
    last = candidate.review_history[-1]
    if (
        last.to_status != ReviewStatus.APPROVED
        or last.claim_id != candidate.claim_id
        or not last.reviewer.strip()
    ):
        return None
    return last


def trusted_candidates(
    candidates: Iterable[CandidateClaim],
) -> list[CandidateClaim]:
    """The only path out of review: approved, current candidates whose
    approval is backed by a recorded review event and whose supporting
    sentence actually states the relation (no blocking uncertainty)."""
    return [
        candidate for candidate in candidates
        if not candidate.stale
        and approval_event(candidate) is not None
        and not BLOCKING_UNCERTAINTY & set(candidate.uncertainty)
    ]


def to_ontology_claim(
    candidate: CandidateClaim,
    conflicts: dict[str, Conflict] | None = None,
) -> Claim | None:
    """Express an approved candidate as an ontology Claim, if it maps directly.

    Returns None when the candidate predicate has no direct ontology
    equivalent (TRADITIONALLY_INDICATED_FOR, which the ontology models
    through a TherapeuticPrinciple, and HAS_CAUTION, which belongs to the
    Component 3 safety boundary). CONTAINS_INGREDIENT maps to the v1.1
    descriptive predicate, which reasoning does not traverse. Verification status:
    DISPUTED if the candidate has conflicts, PRACTITIONER_VERIFIED if a
    practitioner approved it, otherwise LITERATURE_SUPPORTED (a source
    states it). Raises TrustBoundaryError for unapproved candidates.
    """
    if candidate not in trusted_candidates([candidate]):
        raise TrustBoundaryError(
            f"Candidate {candidate.claim_id} is {candidate.review_status.value}"
            + (" and stale" if candidate.stale else "")
            + "; only approved, current candidates can become claims."
        )
    mapping = ONTOLOGY_MAPPING.get(candidate.predicate)
    if mapping is None:
        return None
    predicate, inverted = mapping
    subject, obj = (
        (candidate.object, candidate.subject) if inverted
        else (candidate.subject, candidate.object)
    )
    validate_relationship(
        predicate, subject.concept_type, obj.concept_type, allow_descriptive=True
    )

    approval = approval_event(candidate)
    if candidate.conflict_ids:
        status = VerificationStatus.DISPUTED
    elif approval.reviewer_role == ReviewerRole.PRACTITIONER:
        status = VerificationStatus.PRACTITIONER_VERIFIED
    else:
        status = VerificationStatus.LITERATURE_SUPPORTED

    passage = candidate.passage
    return Claim(
        claim_id=f"CL-{candidate.claim_id}",
        subject_id=subject.concept_id,
        predicate=predicate,
        object_id=obj.concept_id,
        statement=(
            f"Source {passage.source_id} states: {passage.sentence}"
        )[:1000],
        confidence=None,
        verification_status=status,
    )
