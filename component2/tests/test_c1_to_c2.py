
from unittest.mock import MagicMock, patch

import pytest

from app.integration.c1_to_c2 import prepare_c2_request
from app.models.c1_screening_payload import C1ScreeningPayload


def make_payload(
    *,
    risk_level="moderate",
    screening_confidence=0.75,
    symptoms=None,
):
    """Build a synthetic, valid Component 1 payload for testing."""

    return C1ScreeningPayload.model_validate(
        {
            "screening_id": "SCR-TEST-001",
            "session_id": "SESSION-TEST-001",
            "screening_result": {
                "condition": "possible_anaemia",
                "risk_level": risk_level,
                "screening_confidence": screening_confidence,
                "evidence_strength": "limited",
                "status": "simulated_demo",
                "requires_clinician_review": True,
            },
            "hemoglobin": {
                "estimated_g_dl": 10.2,
                "measured_lab_g_dl": None,
                "source": "synthetic_test",
                "clinically_validated": False,
            },
            "modality_results": {
                "conjunctiva": {
                    "model_predictions": [],
                    "quality_score": 0.8,
                    "agreement": True,
                },
                "nailbeds": {
                    "anaemia_class_score": None,
                    "estimated_hb_g_dl": None,
                    "quality_score": None,
                },
                "tongue": {
                    "quality_status": "not_assessed",
                    "anaemia_prediction": None,
                },
                "ppg": {
                    "estimated_hb_g_dl": None,
                    "signal_quality": None,
                    "status": "unavailable",
                },
            },
            "symptoms": symptoms or [],
            "clinical_findings": [],
            "contributing_factors": [],
            "missing_data": [],
            "recommendation": "Synthetic test only.",
            "model_version": "test-model",
            "disclaimer": "Synthetic test data; not for clinical use.",
        }
    )


@pytest.fixture
def driver():
    return MagicMock()


def test_maps_present_symptom_to_canonical_id(driver):
    payload = make_payload(
        symptoms=[
            {"name": "Pale appearance", "present": True},
        ]
    )

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        return_value={
            "status": "resolved",
            "symptom": {
                "symptom_id": "S-PALLOR",
                "name": "Pallor",
            },
            "candidates": [],
        },
    ):
        result = prepare_c2_request(payload, driver)

    assert result["status"] == "ready"
    assert result["request"].symptom_ids == ["S-PALLOR"]
    assert result["request"].risk_tier.value == "moderate"
    assert result["request"].calibrated_confidence == 0.75
    assert result["resolved_symptoms"][0]["canonical_name"] == "Pallor"
    assert result["unresolved_symptoms"] == []


def test_ignores_absent_symptoms_without_resolving_them(driver):
    payload = make_payload(
        symptoms=[
            {"name": "Pallor", "present": False},
        ]
    )

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference"
    ) as resolver:
        result = prepare_c2_request(payload, driver)

    resolver.assert_not_called()
    assert result["status"] == "insufficient_input"
    assert result["request"] is None
    assert result["resolved_symptoms"] == []


@pytest.mark.parametrize(
    ("resolver_result", "expected_status"),
    [
        (
            {
                "status": "not_found",
                "symptom": None,
                "candidates": [],
            },
            "not_found",
        ),
        (
            {
                "status": "ambiguous",
                "symptom": None,
                "candidates": [
                    {"symptom_id": "S-001"},
                    {"symptom_id": "S-002"},
                ],
            },
            "ambiguous",
        ),
    ],
)
def test_does_not_guess_unknown_or_ambiguous_symptoms(
    driver,
    resolver_result,
    expected_status,
):
    payload = make_payload(
        symptoms=[
            {"name": "Uncertain symptom", "present": True},
        ]
    )

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        return_value=resolver_result,
    ):
        result = prepare_c2_request(payload, driver)

    assert result["status"] == "insufficient_input"
    assert result["request"] is None
    assert result["unresolved_symptoms"][0]["status"] == expected_status


def test_preserves_resolved_symptoms_when_another_is_unknown(driver):
    payload = make_payload(
        symptoms=[
            {"name": "Pallor", "present": True},
            {"name": "Unknown symptom", "present": True},
        ]
    )

    def resolve(reference, _driver):
        if reference == "Pallor":
            return {
                "status": "resolved",
                "symptom": {
                    "symptom_id": "S-PALLOR",
                    "name": "Pallor",
                },
                "candidates": [],
            }

        return {
            "status": "not_found",
            "symptom": None,
            "candidates": [],
        }

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        side_effect=resolve,
    ):
        result = prepare_c2_request(payload, driver)

    assert result["status"] == "ready"
    assert result["request"].symptom_ids == ["S-PALLOR"]
    assert len(result["unresolved_symptoms"]) == 1
    assert result["unresolved_symptoms"][0]["status"] == "not_found"


def test_deduplicates_canonical_ids(driver):
    payload = make_payload(
        symptoms=[
            {"name": "Pallor", "present": True},
            {"name": "Pale appearance", "present": True},
        ]
    )

    def resolve(_reference, _driver):
        return {
            "status": "resolved",
            "symptom": {
                "symptom_id": "S-PALLOR",
                "name": "Pallor",
            },
            "candidates": [],
        }

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        side_effect=resolve,
    ):
        result = prepare_c2_request(payload, driver)

    assert result["status"] == "ready"
    assert result["request"].symptom_ids == ["S-PALLOR"]


def test_blocks_unsupported_risk_tier(driver):
    payload = make_payload(risk_level="critical")

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference"
    ) as resolver:
        result = prepare_c2_request(payload, driver)

    resolver.assert_not_called()
    assert result["status"] == "blocked"
    assert result["reason"] == "unsupported_upstream_risk_tier"
    assert result["request"] is None


def test_preserves_missing_upstream_confidence(driver):
    payload = make_payload(
        screening_confidence=None,
        symptoms=[
            {"name": "Pallor", "present": True},
        ],
    )

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        return_value={
            "status": "resolved",
            "symptom": {
                "symptom_id": "S-PALLOR",
                "name": "Pallor",
            },
            "candidates": [],
        },
    ):
        result = prepare_c2_request(payload, driver)

    assert result["status"] == "ready"
    assert result["request"].calibrated_confidence is None


def test_rejects_resolved_record_without_canonical_id(driver):
    payload = make_payload(
        symptoms=[
            {"name": "Pallor", "present": True},
        ]
    )

    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        return_value={
            "status": "resolved",
            "symptom": {"name": "Pallor"},
            "candidates": [],
        },
    ):
        result = prepare_c2_request(payload, driver)

    assert result["status"] == "insufficient_input"
    assert result["request"] is None
    assert (
        result["unresolved_symptoms"][0]["status"]
        == "invalid_graph_record"
    )
