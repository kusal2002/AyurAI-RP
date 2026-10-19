import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.c2 import get_driver
from app.feedback.service import (
    DuplicateFeedbackError,
    build_refinement_query,
    feedback_audit_summary,
)
from app.main import app
from app.models.feedback import PractitionerFeedback
from app.retrieval.service import get_retrieval_service
from c2_test_support import build_pandu_graph, make_retrieval_service


def make(**overrides):
    data = {
        "feedback_id": "fb-1",
        "request_id": "req-1",
        "claim_ids": ["CL-HERB"],
        "candidate_ids": ["H-1"],
        "evidence_ids": ["EV-HERB"],
        "review_outcome": "needs_more_evidence",
        "issue_category": "missing_evidence",
        "rationale": "Synthetic rationale: source needs a second edition.",
        "refinement_terms": ["pandu", " Pandu ", "principle"],
        "suggested_concept_ids": ["TP-1"],
        "reviewer_role": "ayurvedic_practitioner",
        "reviewer_ref": "reviewer-007",
    }
    data.update(overrides)
    return PractitionerFeedback.model_validate(data)


def test_valid_feedback_normalizes_terms():
    feedback = make()

    assert feedback.refinement_terms == ["pandu", "principle"]
    assert feedback.created_at is not None


@pytest.mark.parametrize(
    "override",
    [
        {"claim_ids": [], "candidate_ids": []},
        {"review_outcome": "approve_and_promote"},
        {"issue_category": "unknown"},
        {"rationale": "   "},
        {"reviewer_ref": "Dr Real Name"},
        {"refinement_terms": ["x" * 65]},
        {"claim_ids": ["bad id"]},
        {"unexpected": "field"},
    ],
)
def test_invalid_feedback_rejected(override):
    with pytest.raises(ValidationError):
        make(**override)


def test_refinement_query_is_explicit_and_uses_stored_names():
    graph = build_pandu_graph()
    feedback = make(suggested_concept_ids=["TP-1", "MISSING"])
    query = build_refinement_query(
        feedback, graph.get_concepts(feedback.suggested_concept_ids)
    )

    assert query.terms == ["pandu", "principle", "synthetic principle"]
    assert query.query_text == "pandu ; principle ; synthetic principle"
    assert query.concept_ids == ["TP-1"]
    assert query.unknown_concept_ids == ["MISSING"]


def test_feedback_audit_summary_excludes_rationale():
    line = feedback_audit_summary(make())
    payload = json.loads(line)

    assert payload["feedback_id"] == "fb-1"
    assert "rationale" not in payload
    assert "Synthetic rationale" not in line
    assert "reviewer-007" not in line


@pytest.fixture
def client():
    graph = build_pandu_graph()
    service = make_retrieval_service(graph)
    app.dependency_overrides[get_driver] = lambda: MagicMock()
    app.dependency_overrides[get_retrieval_service] = lambda: service
    with patch(
        "app.feedback.service.get_concepts", side_effect=graph.get_concepts
    ):
        yield TestClient(app)
    app.dependency_overrides.clear()


def test_feedback_endpoint_records_without_modifying_claims(client):
    stored = {
        "feedback_id": "fb-1",
        "linked_claim_ids": ["CL-HERB"],
        "unknown_claim_ids": [],
    }
    with patch("app.api.c2.save_feedback", return_value=stored) as save:
        response = client.post(
            "/api/v1/c2/feedback",
            json=make().model_dump(mode="json"),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["claims_modified"] is False
    assert body["linked_claim_ids"] == ["CL-HERB"]
    assert body["refinement_query"]["query_text"]
    assert body["refinement_retrieval"]["mode"] == "neural_embedding"
    assert body["refinement_retrieval"]["results"]
    save.assert_called_once()


def test_duplicate_feedback_returns_conflict(client):
    with patch(
        "app.api.c2.save_feedback",
        side_effect=DuplicateFeedbackError("exists"),
    ):
        response = client.post(
            "/api/v1/c2/feedback", json=make().model_dump(mode="json")
        )

    assert response.status_code == 409
