import pytest
from pydantic import ValidationError

from app.models.c1_input import Component2ReasoningRequest, RiskTier


def make(**overrides):
    data = {
        "request_id": "req-001",
        "risk_tier": "moderate",
        "calibrated_confidence": 0.82,
        "symptom_ids": ["SYM-001"],
    }
    data.update(overrides)
    return Component2ReasoningRequest.model_validate(data)


def test_accepts_valid_request():
    request = make()

    assert request.request_id == "req-001"
    assert request.risk_tier == RiskTier.MODERATE
    assert request.calibrated_confidence == 0.82
    assert request.symptom_ids == ["SYM-001"]


def test_accepts_screening_confidence_alias():
    data = {
        "risk_tier": "high",
        "screening_confidence": 0.4,
        "symptom_ids": ["SYM-001"],
    }
    request = Component2ReasoningRequest.model_validate(data)

    assert request.calibrated_confidence == 0.4


def test_generates_request_id_when_missing():
    data = {
        "risk_tier": "low",
        "calibrated_confidence": 0.1,
        "symptom_ids": ["SYM-001"],
    }
    request = Component2ReasoningRequest.model_validate(data)

    assert request.request_id.startswith("c2req-")


def test_normalizes_and_deduplicates_symptom_ids():
    request = make(symptom_ids=[" SYM-001 ", "SYM-002", "SYM-001"])

    assert request.symptom_ids == ["SYM-001", "SYM-002"]


def test_accepts_integer_confidence_bounds():
    assert make(calibrated_confidence=0).calibrated_confidence == 0.0
    assert make(calibrated_confidence=1).calibrated_confidence == 1.0


@pytest.mark.parametrize("value", [True, False, "0.5", None, -0.01, 1.01])
def test_rejects_invalid_confidence(value):
    with pytest.raises(ValidationError):
        make(calibrated_confidence=value)


@pytest.mark.parametrize("tier", ["critical", "", "HIGH ", 3, None])
def test_rejects_unsupported_risk_tier(tier):
    with pytest.raises(ValidationError):
        make(risk_tier=tier)


@pytest.mark.parametrize(
    "symptom_ids",
    [[], [""], ["   "], [None], "SYM-001", ["x" * 129]],
)
def test_rejects_invalid_symptom_ids(symptom_ids):
    with pytest.raises(ValidationError):
        make(symptom_ids=symptom_ids)


@pytest.mark.parametrize(
    "request_id", ["", "has space", "../etc", "x" * 129]
)
def test_rejects_malformed_request_id(request_id):
    with pytest.raises(ValidationError):
        make(request_id=request_id)


def test_rejects_unknown_fields_such_as_free_text():
    with pytest.raises(ValidationError):
        make(patient_name="Synthetic Person")


def test_does_not_infer_additional_symptoms():
    request = make(symptom_ids=["SYM-001"])

    assert request.symptom_ids == ["SYM-001"]
