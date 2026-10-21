"""Detection of conflicting candidate claims.

Conflicts are reported and attached to the candidates involved; they are
never resolved automatically, and no candidate is overwritten or dropped
because of one. A conflict's ID is derived from its kind and members, so a
new conflicting passage creates a new, open conflict that needs review.
"""

import hashlib
from collections import defaultdict
from typing import Iterable

from app.knowledge_candidates.models import (
    NEGATION_CUE,
    CandidateClaim,
    Conflict,
    ConflictKind,
    ReviewStatus,
)


_INACTIVE = {ReviewStatus.REJECTED, ReviewStatus.SUPERSEDED}


def _conflict_id(kind: ConflictKind, claim_ids: list[str]) -> str:
    payload = kind.value + "|" + "|".join(sorted(claim_ids))
    return "conf-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def detect_conflicts(candidates: Iterable[CandidateClaim]) -> list[Conflict]:
    active = [
        c for c in candidates
        if c.review_status not in _INACTIVE and not c.stale
    ]
    conflicts: list[Conflict] = []

    by_pair: dict[tuple[str, str], list[CandidateClaim]] = defaultdict(list)
    for candidate in active:
        by_pair[(candidate.subject.concept_id, candidate.object.concept_id)].append(
            candidate
        )
    for (subject_id, object_id), group in sorted(by_pair.items()):
        indications = [c for c in group if c.predicate == "TRADITIONALLY_INDICATED_FOR"]
        cautions = [c for c in group if c.predicate == "HAS_CAUTION"]
        if indications and cautions:
            ids = sorted(c.claim_id for c in indications + cautions)
            conflicts.append(
                Conflict(
                    conflict_id=_conflict_id(ConflictKind.INDICATION_VS_CAUTION, ids),
                    kind=ConflictKind.INDICATION_VS_CAUTION,
                    claim_ids=ids,
                    description=(
                        f"{subject_id} is described as indicated for "
                        f"{object_id} in {len(indications)} passage(s) and with "
                        f"a caution in {len(cautions)} passage(s)."
                    ),
                )
            )

    by_relation: dict[tuple[str, str, str], list[CandidateClaim]] = defaultdict(list)
    for candidate in active:
        by_relation[candidate.relation_key].append(candidate)
    for key, group in sorted(by_relation.items()):
        negated = [c for c in group if NEGATION_CUE in c.uncertainty]
        plain = [c for c in group if NEGATION_CUE not in c.uncertainty]
        if negated and plain:
            ids = sorted(c.claim_id for c in group)
            conflicts.append(
                Conflict(
                    conflict_id=_conflict_id(ConflictKind.POLARITY, ids),
                    kind=ConflictKind.POLARITY,
                    claim_ids=ids,
                    description=(
                        f"{' '.join(key)} appears in {len(plain)} passage(s) "
                        f"and with negation wording in {len(negated)}."
                    ),
                )
            )
    return conflicts


def attach_conflicts(
    candidates: dict[str, CandidateClaim],
    conflicts: list[Conflict],
    previous: dict[str, Conflict] | None = None,
) -> dict[str, Conflict]:
    """Link conflicts to their candidates, keeping earlier acknowledgements.

    Returns the conflicts by ID. Candidates are updated in place.
    """
    previous = previous or {}
    current: dict[str, Conflict] = {}
    for conflict in conflicts:
        earlier = previous.get(conflict.conflict_id)
        if earlier is not None:
            conflict = conflict.model_copy(
                update={
                    "status": earlier.status,
                    "acknowledged_by": earlier.acknowledged_by,
                }
            )
        current[conflict.conflict_id] = conflict

    members: dict[str, list[str]] = defaultdict(list)
    for conflict in current.values():
        for claim_id in conflict.claim_ids:
            members[claim_id].append(conflict.conflict_id)
    for claim_id, candidate in candidates.items():
        candidates[claim_id] = candidate.model_copy(
            update={"conflict_ids": sorted(members.get(claim_id, []))}
        )
    return current
