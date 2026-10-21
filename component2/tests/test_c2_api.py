import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from app.api.c2 import get_driver
from app.main import app
from app.retrieval.service import get_retrieval_service
from c2_test_support import (
    FailingEncoder,
    FakeGraph,
    build_pandu_graph,
    make_retrieval_service,
)


VALID_BODY = {
    "request_id": "req-api-1",
    "risk_tier": "moderate",
    "calibrated_confidence": 0.7,
    "symptom_ids": ["S-PALLOR", " S-PALLOR "],
}


@pytest.fixture
def client_for():
    clients = []

    def make(graph, encoder=None):
        app.dependency_overrides[get_driver] = lambda: MagicMock()
        service = make_retrieval_service(graph, encoder=encoder)
        app.dependency_overrides[get_retrieval_service] = lambda: service
        stack = graph.patched()
        stack.__enter__()
        clients.append(stack)
        return TestClient(app)

    yield make

    for stack in clients:
        stack.__exit__(None, None, None)
    app.dependency_overrides.clear()


def test_valid_request_returns_structured_output(client_for):
    client = client_for(build_pandu_graph())
    response = client.post("/api/v1/c2/reasoning", json=VALID_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-api-1"
    assert body["input_symptom_ids"] == ["S-PALLOR"]
    assert body["upstream"]["calibrated_confidence"] == 0.7
    assert body["retrieval"]["mode"] == "neural_embedding"
    assert body["abstention"]["abstain"] is False
    assert body["medical_conclusion"] is None
    candidate = body["candidates"][0]
    assert candidate["claim_ids"]
    assert candidate["supporting_evidence_ids"]
    assert candidate["sufficiency"]["status"] == "sufficient_for_review"
    assert candidate["ranking"]["label"] == (
        "experimental_ranking_score_not_clinical_confidence"
    )


@pytest.mark.parametrize(
    "override",
    [
        {"risk_tier": "critical"},
        {"calibrated_confidence": True},
        {"calibrated_confidence": 1.5},
        {"symptom_ids": []},
        {"patient_name": "Synthetic Person"},
    ],
)
def test_invalid_request_is_rejected(client_for, override):
    client = client_for(build_pandu_graph())
    response = client.post(
        "/api/v1/c2/reasoning", json={**VALID_BODY, **override}
    )

    assert response.status_code == 422


def test_missing_symptom_abstains(client_for):
    client = client_for(build_pandu_graph())
    response = client.post(
        "/api/v1/c2/reasoning",
        json={**VALID_BODY, "symptom_ids": ["S-UNKNOWN"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sufficiency_status"] == "out_of_scope"
    assert body["abstention"]["abstain"] is True
    assert body["candidates"] == []


def test_empty_knowledge_graph(client_for):
    client = client_for(FakeGraph())
    response = client.post("/api/v1/c2/reasoning", json=VALID_BODY)

    assert response.status_code == 200
    assert response.json()["candidates"] == []
    assert response.json()["abstention"]["abstain"] is True


def test_model_unavailable_is_reported_cleanly(client_for):
    client = client_for(build_pandu_graph(), encoder=FailingEncoder())
    response = client.post("/api/v1/c2/reasoning", json=VALID_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["retrieval"]["mode"] == "unavailable"
    assert "semantic_retrieval_unavailable" in body["uncertainty_flags"]


def test_graph_unavailable_returns_503_without_details(client_for):
    client = client_for(build_pandu_graph())
    with patch(
        "app.api.c2.run_component2_reasoning",
        side_effect=ServiceUnavailable("bolt://secret-host:7687 refused"),
    ):
        response = client.post("/api/v1/c2/reasoning", json=VALID_BODY)

    assert response.status_code == 503
    assert "secret-host" not in response.text
    assert "Traceback" not in response.text


def test_missing_database_configuration_returns_503():
    app.dependency_overrides.clear()
    with patch(
        "app.api.c2.get_neo4j_driver",
        side_effect=RuntimeError("Neo4j configuration is missing."),
    ):
        response = TestClient(app).post(
            "/api/v1/c2/reasoning", json=VALID_BODY
        )

    assert response.status_code == 503
    assert "NEO4J" not in response.text


def test_component3_handoff_endpoint(client_for):
    client = client_for(build_pandu_graph())
    response = client.post(
        "/api/v1/c2/reasoning/component3-handoff", json=VALID_BODY
    )

    assert response.status_code == 200
    body = response.json()
    assert body["handoff_schema_version"] == "c2-to-c3/0.1.0"
    assert body["safety_assessment_performed_by_component2"] is False
    assert body["candidates"][0]["evidence_ids"]


def test_audit_log_written_without_raw_input(client_for, caplog):
    client = client_for(build_pandu_graph())
    with caplog.at_level(logging.INFO, logger="ayurai.c2.audit"):
        client.post("/api/v1/c2/reasoning", json=VALID_BODY)

    audit_lines = [
        r.getMessage() for r in caplog.records if r.name == "ayurai.c2.audit"
    ]
    assert len(audit_lines) == 1
    assert "req-api-1" in audit_lines[0]
    assert "S-PALLOR" not in audit_lines[0]
    assert "moderate" not in audit_lines[0]


def test_importing_api_does_not_load_model():
    service = get_retrieval_service()

    assert service._encoder.is_loaded is False
