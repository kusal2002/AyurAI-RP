"""Provisional risk-context gating: the Recommend / Caution / Abstain decision.

Implements Option B of docs/design_risk_tier_integration.md (approved
decisions R-D1 to R-D3, 2026-10-20). The Component 1 risk tier and
calibrated confidence decide whether the request-level *decision* needs
caution and escalation (FR9, FR10). They never change:

- candidate ranking scores or order (the score stays independent of C1
  confidence; see ranking.py),
- per-candidate sufficiency or forward/withhold dispositions,
- the evidence-based `sufficiency_status`.

These rules are a safety and communication policy, not Ayurvedic
knowledge: no relation between a risk tier and any candidate is assumed.
All thresholds are provisional pending supervisor review and SO5
calibration.

Decision mapping (design §5.2):

| sufficiency_status            | risk rules triggered | decision             |
|-------------------------------|----------------------|----------------------|
| sufficient_for_review         | none                 | recommend_for_review |
| sufficient_for_review         | any                  | caution              |
| conflicting / unverified      | any                  | caution              |
| insufficient / out_of_scope   | any                  | abstain              |
"""

from dataclasses import dataclass

from app.models.c1_input import RiskTier
from app.models.c2_output import Decision, RiskContext, RiskRule, SufficiencyStatus


ESCALATION_TEXT = {
    RiskRule.HIGH_TIER: (
        "Component 1 reports a high anaemia risk tier: practitioner review "
        "and conventional clinical assessment are recommended before any "
        "Ayurvedic candidate is considered."
    ),
    RiskRule.CONFIDENCE_MISSING: (
        "Component 1 supplied no screening confidence, so the reliability "
        "of the risk tier is unknown; interpret with caution."
    ),
    RiskRule.LOW_CONFIDENCE: (
        "Component 1 screening confidence is low; the risk tier may be "
        "unreliable; interpret with caution."
    ),
    RiskRule.URGENT_REVIEW: (
        "Component 1 flagged urgent clinician review: conventional clinical "
        "care must not be delayed; any Ayurvedic candidate is secondary."
    ),
}


@dataclass(frozen=True)
class RiskContextPolicy:
    policy_id: str = "prototype-risk-context-v0.1-provisional"
    # R3 (R-D2): below this C1 confidence the decision needs caution.
    low_confidence_threshold: float = 0.5
    # R1 (R-D2): a high tier needs caution (not abstention).
    caution_on_high_tier: bool = True
    # R4 (R-D3): high tier with missing confidence abstains only if True.
    abstain_on_high_tier_without_confidence: bool = False


def evaluate_risk_context(
    risk_tier: RiskTier,
    calibrated_confidence: float | None,
    policy: RiskContextPolicy,
    urgent_clinician_review: bool = False,
) -> RiskContext:
    rules: list[RiskRule] = []
    if urgent_clinician_review:
        rules.append(RiskRule.URGENT_REVIEW)
    if policy.caution_on_high_tier and risk_tier == RiskTier.HIGH:
        rules.append(RiskRule.HIGH_TIER)
    if calibrated_confidence is None:
        rules.append(RiskRule.CONFIDENCE_MISSING)
    elif calibrated_confidence < policy.low_confidence_threshold:
        rules.append(RiskRule.LOW_CONFIDENCE)
    return RiskContext(
        risk_tier=risk_tier,
        calibrated_confidence=calibrated_confidence,
        rules_triggered=rules,
        escalation=[ESCALATION_TEXT[rule] for rule in rules],
        policy_id=policy.policy_id,
    )


_ABSTAIN_STATUSES = {
    SufficiencyStatus.INSUFFICIENT_EVIDENCE,
    SufficiencyStatus.OUT_OF_SCOPE,
}


def decide(
    sufficiency_status: SufficiencyStatus,
    risk: RiskContext,
    policy: RiskContextPolicy,
) -> tuple[Decision, list[str]]:
    """Return the decision and the machine-readable reasons for it."""
    if sufficiency_status in _ABSTAIN_STATUSES:
        return Decision.ABSTAIN, [f"evidence:{sufficiency_status.value}"]
    if (
        policy.abstain_on_high_tier_without_confidence
        and RiskRule.HIGH_TIER in risk.rules_triggered
        and RiskRule.CONFIDENCE_MISSING in risk.rules_triggered
    ):
        return Decision.ABSTAIN, ["critical_upstream_information_missing"]

    reasons: list[str] = []
    if sufficiency_status != SufficiencyStatus.SUFFICIENT_FOR_REVIEW:
        reasons.append(f"evidence:{sufficiency_status.value}")
    reasons += [f"risk:{rule.value}" for rule in risk.rules_triggered]
    if reasons:
        return Decision.CAUTION, reasons
    return Decision.RECOMMEND_FOR_REVIEW, []
