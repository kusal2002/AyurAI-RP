"""Option B: Recommend / Caution / Abstain decision gated by C1 risk context.

Covers every row of docs/design_risk_tier_integration.md §5.2 and the
invariants: ranking scores, candidate sufficiency and dispositions never
depend on the risk tier or the C1 confidence.
"""

import json

import pytest

from app.governance.audit import build_audit_record
from app.models.c1_input import Component2ReasoningRequest, RiskTier
from app.models.c2_output import Decision, RiskRule, SufficiencyStatus
from app.models.c3_handoff import build_component3_handoff
from app.reasoning.pipeline import run_component2_reasoning
from app.reasoning.risk_context import RiskContextPolicy, decide, evaluate_risk_context
from c2_test_support import FakeGraph, build_pandu_graph, make_retrieval_service

POLICY = RiskContextPolicy()


# --- rules -------------------------------------------------------------------

@pytest.mark.parametrize("tier, confidence, rules", [
    (RiskTier.LOW, 0.9, []),
    (RiskTier.MODERATE, 0.9, []),
    (RiskTier.HIGH, 0.9, [RiskRule.HIGH_TIER]),
    (RiskTier.MODERATE, None, [RiskRule.CONFIDENCE_MISSING]),
    (RiskTier.MODERATE, 0.49, [RiskRule.LOW_CONFIDENCE]),
    (RiskTier.MODERATE, 0.5, []),  # threshold is exclusive
    (RiskTier.HIGH, None, [RiskRule.HIGH_TIER, RiskRule.CONFIDENCE_MISSING]),
    (RiskTier.LOW, 0.2, [RiskRule.LOW_CONFIDENCE]),  # a low tier is not reassurance
])
def test_rules_triggered(tier, confidence, rules):
    context = evaluate_risk_context(tier, confidence, POLICY)
    assert context.rules_triggered == rules
    assert len(context.escalation) == len(rules)
    assert context.policy_id == POLICY.policy_id


def test_high_tier_escalation_names_conventional_assessment():
    context = evaluate_risk_context(RiskTier.HIGH, 0.9, POLICY)
    assert "conventional clinical assessment" in context.escalation[0]


# --- decision table (design §5.2) ---------------------------------------------

def _ctx(tier=RiskTier.MODERATE, confidence=0.9, policy=POLICY):
    return evaluate_risk_context(tier, confidence, policy)


@pytest.mark.parametrize("status, tier, confidence, decision", [
    (SufficiencyStatus.SUFFICIENT_FOR_REVIEW, RiskTier.MODERATE, 0.9, Decision.RECOMMEND_FOR_REVIEW),
    (SufficiencyStatus.SUFFICIENT_FOR_REVIEW, RiskTier.HIGH, 0.9, Decision.CAUTION),
    (SufficiencyStatus.SUFFICIENT_FOR_REVIEW, RiskTier.MODERATE, None, Decision.CAUTION),
    (SufficiencyStatus.SUFFICIENT_FOR_REVIEW, RiskTier.LOW, 0.3, Decision.CAUTION),
    (SufficiencyStatus.CONFLICTING_EVIDENCE, RiskTier.LOW, 0.9, Decision.CAUTION),
    (SufficiencyStatus.UNVERIFIED_CLAIMS, RiskTier.MODERATE, 0.9, Decision.CAUTION),
    (SufficiencyStatus.INSUFFICIENT_EVIDENCE, RiskTier.HIGH, None, Decision.ABSTAIN),
    (SufficiencyStatus.OUT_OF_SCOPE, RiskTier.LOW, 0.9, Decision.ABSTAIN),
])
def test_decision_table(status, tier, confidence, decision):
    result, reasons = decide(status, _ctx(tier, confidence), POLICY)
    assert result == decision
    if decision == Decision.RECOMMEND_FOR_REVIEW:
        assert reasons == []
    else:
        assert reasons


def test_reasons_name_evidence_and_risk_separately():
    _, reasons = decide(SufficiencyStatus.CONFLICTING_EVIDENCE, _ctx(RiskTier.HIGH, None), POLICY)
    assert reasons == [
        "evidence:conflicting_evidence",
        "risk:upstream_high_risk",
        "risk:upstream_confidence_missing",
    ]


def test_r4_is_off_by_default_and_configurable():
    context = _ctx(RiskTier.HIGH, None)
    assert decide(SufficiencyStatus.SUFFICIENT_FOR_REVIEW, context, POLICY)[0] == Decision.CAUTION
    strict = RiskContextPolicy(abstain_on_high_tier_without_confidence=True)
    decision, reasons = decide(SufficiencyStatus.SUFFICIENT_FOR_REVIEW, _ctx(RiskTier.HIGH, None, strict), strict)
    assert decision == Decision.ABSTAIN and reasons == ["critical_upstream_information_missing"]


# --- pipeline invariants ----------------------------------------------------------

def _run(graph, tier="moderate", confidence=0.9):
    request = Component2ReasoningRequest(
        request_id="req-risk-1", risk_tier=tier, calibrated_confidence=confidence,
        symptom_ids=["S-PALLOR"],
    )
    with graph.patched():
        return run_component2_reasoning(request, retrieval_service=make_retrieval_service(graph))


def _ranking_view(output):
    return [
        (c.candidate_id, c.rank, c.ranking.score, c.ranking.components,
         c.disposition, c.sufficiency.status)
        for c in output.candidates
    ]


def test_tier_and_confidence_never_change_ranking_or_dispositions():
    variants = [
        ("low", 0.95), ("moderate", 0.9), ("high", 0.99), ("high", None), ("moderate", 0.01),
    ]
    views = [_ranking_view(_run(build_pandu_graph(), tier, conf)) for tier, conf in variants]
    assert views[0] and all(view == views[0] for view in views)


def test_pipeline_decisions_follow_risk_context():
    graph = build_pandu_graph()
    plain = _run(graph, "moderate", 0.9)
    assert plain.sufficiency_status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW
    assert plain.decision == Decision.RECOMMEND_FOR_REVIEW
    assert plain.risk_context.rules_triggered == []

    high = _run(build_pandu_graph(), "high", 0.9)
    assert high.sufficiency_status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW  # evidence status unchanged
    assert high.decision == Decision.CAUTION
    assert high.review_required is True
    caution = [s for s in high.explanation if s.kind == "caution"]
    assert caution and "conventional clinical assessment" in caution[0].text
    assert high.abstention.abstain is False  # caution is not abstention

    missing = _run(build_pandu_graph(), "low", None)
    assert missing.decision == Decision.CAUTION
    assert missing.risk_context.rules_triggered == [RiskRule.CONFIDENCE_MISSING]


def test_conflicting_evidence_is_caution_and_empty_graph_abstains():
    conflicting = _run(build_pandu_graph(herb_contradicts=("EV-HERB-CON",)), "moderate", 0.9)
    # The decision table works on the request-level status: other
    # candidates are sufficient, so the request recommends for review while
    # the conflicting herb itself stays withheld.
    herb = next(c for c in conflicting.candidates if c.candidate_id == "H-1")
    assert herb.sufficiency.status == SufficiencyStatus.CONFLICTING_EVIDENCE
    assert herb.disposition.value == "withheld_pending_review"
    assert conflicting.sufficiency_status == SufficiencyStatus.SUFFICIENT_FOR_REVIEW
    assert conflicting.decision == Decision.RECOMMEND_FOR_REVIEW

    # Only the conflicting herb path left: request-level conflict -> caution.
    graph = build_pandu_graph(herb_contradicts=("EV-HERB-CON",))
    for claim_id in ("CL-FORM", "CL-DIET", "CL-LIFE"):
        del graph.claims[claim_id]
    only_conflicting = _run(graph, "moderate", 0.9)
    assert only_conflicting.sufficiency_status == SufficiencyStatus.CONFLICTING_EVIDENCE
    assert only_conflicting.decision == Decision.CAUTION
    assert only_conflicting.decision_reasons == ["evidence:conflicting_evidence"]

    empty = _run(FakeGraph(), "high", 0.9)
    assert empty.sufficiency_status == SufficiencyStatus.OUT_OF_SCOPE
    assert empty.decision == Decision.ABSTAIN
    assert empty.decision_reasons == ["evidence:out_of_scope"]


def test_audit_logs_decision_but_not_risk_rules_or_tier():
    output = _run(build_pandu_graph(), "high", 0.91)
    record = json.loads(build_audit_record(output).model_dump_json())
    assert record["decision"] == "caution"
    assert record["risk_policy_id"] == POLICY.policy_id
    text = json.dumps(record)
    assert "upstream_high_risk" not in text and "0.91" not in text and '"high"' not in text


def test_c3_handoff_contract_is_unchanged():
    handoff = build_component3_handoff(_run(build_pandu_graph(), "high", 0.9))
    assert "risk_context" not in handoff.model_dump()  # R-D5 not approved


def test_output_schema_version_bumped():
    assert _run(build_pandu_graph()).schema_version == "c2-output/0.4.0"
