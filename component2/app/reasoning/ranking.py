"""Provisional, configurable evidence-weighted ranking of candidates.

No approved or clinically validated weighting formula exists in the
project. This module implements a transparent PROTOTYPE policy so that
candidates can be ordered for review. The resulting score is an
experimental engineering ranking value: it is not clinical confidence and
does not predict safety, efficacy or truth. All weights are provisional
and isolated in RankingPolicy for supervisor/practitioner revision.

Path score (each component reported separately):
  status        = w_status  * min(status weight over claims in the path)
  support       = w_support * min over claims of
                  min(independent supporting sources, cap) / cap
  contradiction = -w_contra * max over claims of
                  min(contradicting sources, cap) / cap
  provenance    = -w_prov   * share of supporting references in the path
                  with incomplete provenance
  retrieval     = w_retr    * min over claims of retrieval similarity
                  (clipped to [0, 1]; 0 when unavailable)

A chain is treated as only as strong as its weakest claim, so the path
uses minimums. The candidate takes its best path. Screening confidence
from Component 1 is never an input.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from app.models.c2_output import CandidatePath, EvidenceReference, RankingBreakdown


@dataclass(frozen=True)
class RankingPolicy:
    policy_id: str = "prototype-ranking-v0.1-provisional"
    status_weights: Mapping[str, float] = field(
        default_factory=lambda: MappingProxyType(
            {
                "practitioner_verified": 1.0,
                "literature_supported": 0.7,
                "unverified": 0.2,
                "disputed": 0.0,
            }
        )
    )
    w_status: float = 0.4
    w_support: float = 0.3
    support_source_cap: int = 3
    w_contradiction: float = 0.3
    contradiction_source_cap: int = 3
    w_provenance: float = 0.1
    w_retrieval: float = 0.2


def source_key(reference: EvidenceReference) -> str:
    """Key used to count independently identifiable sources.

    Two evidence records citing the same source (same source name and
    citation/URL/title) count once. Without a source name the evidence_id
    is used, so unidentified sources are never merged.
    """
    if not reference.source_name:
        return f"id:{reference.evidence_id}"
    locator = reference.citation or reference.source_url or reference.title
    return (
        f"src:{reference.source_name.casefold()}|"
        f"{(locator or reference.evidence_id).casefold()}"
    )


def independent_source_count(references: list[EvidenceReference]) -> int:
    return len({source_key(reference) for reference in references})


def score_path(
    path: CandidatePath,
    policy: RankingPolicy,
) -> dict[str, float]:
    claims = path.claims
    status = min(
        policy.status_weights.get(claim.verification_status, 0.0)
        for claim in claims
    )
    support = min(
        min(
            independent_source_count(claim.supporting_evidence),
            policy.support_source_cap,
        ) / policy.support_source_cap
        for claim in claims
    )
    contradiction = max(
        min(
            independent_source_count(claim.contradicting_evidence),
            policy.contradiction_source_cap,
        ) / policy.contradiction_source_cap
        for claim in claims
    )
    supporting_refs = [
        reference
        for claim in claims
        for reference in claim.supporting_evidence
    ]
    incomplete_share = (
        sum(not ref.provenance_complete for ref in supporting_refs)
        / len(supporting_refs)
        if supporting_refs
        else 0.0
    )
    similarities = [claim.retrieval_similarity for claim in claims]
    retrieval = (
        min(max(0.0, min(1.0, s)) for s in similarities)
        if similarities and all(s is not None for s in similarities)
        else 0.0
    )

    components = {
        "status": policy.w_status * status,
        "support": policy.w_support * support,
        "contradiction": -policy.w_contradiction * contradiction,
        "provenance": -policy.w_provenance * incomplete_share,
        "retrieval": policy.w_retrieval * retrieval,
    }
    # Adding 0.0 normalizes -0.0 for readable output.
    return {key: round(value, 4) + 0.0 for key, value in components.items()}


def rank_candidate(
    paths: list[CandidatePath],
    policy: RankingPolicy,
) -> RankingBreakdown:
    """Score every path and return the best path's breakdown."""
    if not paths:
        raise ValueError("A candidate must have at least one path.")

    scored = []
    for path in paths:
        components = score_path(path, policy)
        total = round(sum(components.values()), 4)
        scored.append(
            (
                -total,
                len(path.claims),
                tuple(claim.claim_id for claim in path.claims),
                components,
                total,
            )
        )

    best = min(
        scored,
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            tuple(sorted(item[3].items())),
        ),
    )
    return RankingBreakdown(
        score=best[4],
        components=best[3],
        policy_id=policy.policy_id,
    )
