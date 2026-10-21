
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from app.api.c1_c2 import get_driver
from app.api.c2 import get_driver as c2_get_driver
from app.main import app
from app.retrieval.service import get_retrieval_service
from c2_test_support import build_pandu_graph, make_retrieval_service


VALID_C1_BODY = {
    "screening_id": "SCR-TEST-001",
    "session_id": "SESSION-TEST-001",
    "screening_result": {
        "condition": "possible_anaemia",
        "risk_level": "moderate",
        "screening_confidence": 0.75,
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
    "symptoms": [{"name": "Pallor", "present": True}],
    "clinical_findings": [],
    "contributing_factors": [],
    "missing_data": [],
    "recommendation": "Synthetic test only.",
    "model_version": "test-model",
    "disclaimer": "Synthetic test data; not for clinical use.",
}


@pytest.fixture
def integration_client():
    graph = build_pandu_graph()
    app.dependency_overrides[c2_get_driver] = lambda: object()
    app.dependency_overrides[get_retrieval_service] = lambda: (
        make_retrieval_service(graph)
    )

    with graph.patched():
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


def test_c1_reasoning_runs_pipeline_after_mapping(integration_client):
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
        response = integration_client.post(
            "/api/v1/c1/reasoning", json=VALID_C1_BODY
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["screening_id"] == "SCR-TEST-001"
    assert body["mapping"]["status"] == "ready"
    assert body["mapping"]["resolved_symptoms"][0]["symptom_id"] == "S-PALLOR"
    assert body["reasoning"]["input_symptom_ids"] == ["S-PALLOR"]


def test_c1_reasoning_stops_when_symptoms_are_unresolved(
    integration_client,
):
    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        return_value={
            "status": "not_found",
            "symptom": None,
            "candidates": [],
        },
    ), patch("app.api.c1_c2._run") as run:
        response = integration_client.post(
            "/api/v1/c1/reasoning", json=VALID_C1_BODY
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_input"
    assert body["reasoning"] is None
    assert body["mapping"]["unresolved_symptoms"][0]["status"] == "not_found"
    run.assert_not_called()


def test_c1_reasoning_blocks_unsupported_risk_tier(integration_client):
    body = {
        **VALID_C1_BODY,
        "screening_result": {
            **VALID_C1_BODY["screening_result"],
            "risk_level": "critical",
        },
    }

    with patch("app.integration.c1_to_c2.resolve_symptom_reference") as resolver:
        response = integration_client.post(
            "/api/v1/c1/reasoning", json=body
        )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["reasoning"] is None
    resolver.assert_not_called()


def test_c1_reasoning_maps_graph_unavailable_to_503(integration_client):
    with patch(
        "app.integration.c1_to_c2.resolve_symptom_reference",
        side_effect=ServiceUnavailable("private database address"),
    ):
        response = integration_client.post(
            "/api/v1/c1/reasoning", json=VALID_C1_BODY
        )

    assert response.status_code == 503
    assert "private database address" not in response.text


def test_existing_c1_screening_result_endpoint_is_preserved(
    integration_client,
):
    response = integration_client.post(
        "/api/v1/c1/screening-result", json=VALID_C1_BODY
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["screening_id"] == "SCR-TEST-001"
