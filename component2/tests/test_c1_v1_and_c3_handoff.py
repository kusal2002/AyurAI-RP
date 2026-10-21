"""Component 1 `c1.screening.v1` input and the agreed C2 -> C3 handoff."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.c2 import get_driver as c2_get_driver
from app.main import app
from app.models.c1_input import RiskTier
from app.models.c1_screening_v1 import C1ScreeningPayloadV1, screening_inputs
from app.models.c2_output import Decision, RiskRule
from app.models.c3_handoff import build_component3_handoff
from app.reasoning.risk_context import RiskContextPolicy, evaluate_risk_context
from app.retrieval.service import get_retrieval_service
from app.models.c1_input import Component2ReasoningRequest
from app.reasoning.pipeline import run_component2_reasoning
from c2_test_support import build_pandu_graph, make_retrieval_service


def run(graph):
    request = Component2ReasoningRequest(
        request_id="req-v1-test", risk_tier="moderate", calibrated_confidence=0.9, symptom_ids=["S-PALLOR"]
    )
    with graph.patched():
        return run_component2_reasoning(request, retrieval_service=make_retrieval_service(graph))

V1_BODY = {
    "schema_version": "c1.screening.v1",
    "screening_id": "C1-SYNTH-007",
    "session_id": "demo_synthetic_007",
    "synthetic_fixture": True,
    "screening_result": {
        "risk_level": "high",
        "confidence_percent": None,
        "experimental_reliability_score": 0.74,
        "reliability_score_is_calibrated": False,
        "clinician_review_required": True,
    },
    "symptoms": ["pallor", "heavy_active_bleeding"],
    "questionnaire_status": {"urgent_clinician_review": True},
    "modality_evidence": {"images": {"regions": {}}},
    "missing_modalities": [],
    "doctor_summary": "FICTIONAL CASE",
}


def _resolver(name, driver=None):
    if name.lower() == "pallor":
        return {"status": "resolved", "symptom": {"symptom_id": "S-PALLOR", "name": "pallor"}, "candidates": []}
    return {"status": "not_found", "symptom": None, "candidates": []}


def test_v1_inputs_never_use_the_uncalibrated_reliability_score():
    inputs = screening_inputs(C1ScreeningPayloadV1.model_validate(V1_BODY))
    assert inputs["calibrated_confidence"] is None
    assert inputs["present_symptoms"] == ["pallor", "heavy active bleeding"]
    assert inputs["urgent_clinician_review"] is True
    with_percent = {**V1_BODY, "screening_result": {**V1_BODY["screening_result"], "confidence_percent": 84}}
    assert screening_inputs(C1ScreeningPayloadV1.model_validate(with_percent))["calibrated_confidence"] == 0.84


def test_urgent_review_rule_gates_the_decision_to_caution():
    policy = RiskContextPolicy()
    risk = evaluate_risk_context(RiskTier.LOW, 0.9, policy, urgent_clinician_review=True)
    assert risk.rules_triggered == [RiskRule.URGENT_REVIEW]
    assert "must not be delayed" in risk.escalation[0]


def test_handoff_follows_the_agreed_c3_format():
    handoff = build_component3_handoff(run(build_pandu_graph()), urgent_clinician_review=True)
    body = handoff.model_dump(mode="json")
    assert body["handoff_schema_version"] == "c2-to-c3/0.1.0"
    assert body["upstream"]["urgent_clinician_review"] is True
    assert body["review_required"] is True
    assert "not a diagnosis" in body["ayurvedic_interpretation"]
    assert {c["category"] for c in body["candidates"]} <= {"Herb", "Formulation"}
    assert set(body["non_medicinal_candidate_ids"]) == {"D-1", "L-1"}
    herb = next(c for c in body["candidates"] if c["candidate_id"] == "H-1")
    assert herb["dose"] is None
    assert herb["rationale"] and {"claim_id", "text"} <= herb["rationale"][0].keys()
    assert herb["evidence_ids"] and herb["claim_ids"]


def test_botanical_name_comes_only_from_the_graph():
    graph = build_pandu_graph()
    graph.concepts["H-1"][1]["botanical_name_as_stated"] = "Boerhavia diffusa"
    handoff = build_component3_handoff(run(graph))
    names = {c.candidate_id: c.botanical_name for c in handoff.candidates}
    assert names["H-1"] == "Boerhavia diffusa"
    assert names["F-1"] is None


@pytest.fixture
def client():
    graph = build_pandu_graph()
    app.dependency_overrides[c2_get_driver] = lambda: object()
    app.dependency_overrides[get_retrieval_service] = lambda: make_retrieval_service(graph)
    with graph.patched(), patch("app.integration.c1_to_c2.resolve_symptom_reference", side_effect=_resolver):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()


def test_c1_reasoning_accepts_v1_and_reports_unknown_symptoms(client):
    body = client.post("/api/v1/c1/reasoning", json=V1_BODY).json()
    assert body["status"] == "completed"
    assert body["upstream_flags"] == {
        "input_format": "c1.screening.v1", "clinician_review_required": True, "urgent_clinician_review": True,
    }
    assert body["mapping"]["unresolved_symptoms"][0]["input_name"] == "heavy active bleeding"
    reasoning = body["reasoning"]
    assert reasoning["upstream"]["calibrated_confidence"] is None
    assert reasoning["decision"] == Decision.CAUTION.value
    assert "risk:upstream_urgent_clinician_review" in reasoning["decision_reasons"]


def test_c1_component3_handoff_endpoint(client):
    body = client.post("/api/v1/c1/component3-handoff", json=V1_BODY).json()
    assert body["status"] == "completed" and "reasoning" not in body
    handoff = body["handoff"]
    assert handoff["upstream"] == {"risk_tier": "high", "calibrated_confidence": None, "urgent_clinician_review": True}
    assert handoff["candidates"] and all(c["dose"] is None for c in handoff["candidates"])


def test_v1_without_present_symptoms_returns_no_handoff(client):
    body = client.post("/api/v1/c1/component3-handoff", json={**V1_BODY, "symptoms": []}).json()
    assert body["status"] == "insufficient_input" and body["handoff"] is None


def test_v1_payload_is_validated(client):
    bad = {**V1_BODY, "screening_result": {**V1_BODY["screening_result"], "confidence_percent": 140}}
    assert client.post("/api/v1/c1/reasoning", json=bad).status_code == 422
