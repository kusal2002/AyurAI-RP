from unittest.mock import patch

import pytest

from app.reasoning.symptom_reasoner import reason_about_symptoms


SYMPTOM = {
    "symptom_id": "SYM-001",
    "name": "Synthetic test symptom",
    "aliases": [],
}

INDICATES_CLAIM = {
    "claim_id": "CLAIM-001",
    "subject_id": "SYM-001",
    "predicate": "INDICATES",
    "object_id": "ROGA-001",
    "statement": "Synthetic symptom-to-Roga test claim.",
    "verification_status": "unverified",
}

EVALUATION = {
    "claim": INDICATES_CLAIM,
    "verification_status": "unverified",
    "stored_confidence": None,
    "supporting_evidence": [],
    "contradicting_evidence": [],
    "evidence_summary": {
        "supporting_count": 0,
        "contradicting_count": 0,
    },
    "reasoning_notes": ["No supporting evidence is linked."],
    "medical_conclusion": None,
}


def test_reason_about_symptoms_evaluates_indicates_claims():
    with (
        patch(
            "app.reasoning.symptom_reasoner.get_symptom",
            return_value=SYMPTOM,
        ),
        patch(
            "app.reasoning.symptom_reasoner.get_claims_for_concept",
            return_value=[
                {
                    "claim": INDICATES_CLAIM,
                    "role": "subject",
                }
            ],
        ) as claims_mock,
        patch(
            "app.reasoning.symptom_reasoner.evaluate_claim",
            return_value=EVALUATION,
        ) as evaluate_mock,
    ):
        result = reason_about_symptoms(["SYM-001"])

    assert result["summary"] == {
        "requested_symptom_count": 1,
        "unique_symptom_count": 1,
        "found_symptom_count": 1,
        "indicates_claim_count": 1,
    }

    claim_result = result["results"][0]["indicates_claims"][0]

    assert claim_result["claim_id"] == "CLAIM-001"
    assert claim_result["roga_id"] == "ROGA-001"
    assert claim_result["verification_status"] == "unverified"
    assert claim_result["evaluation"] == EVALUATION
    assert result["medical_conclusion"] is None

    claims_mock.assert_called_once_with("SYM-001", None)
    evaluate_mock.assert_called_once_with("CLAIM-001", None)


def test_reason_about_symptoms_ignores_irrelevant_claims():
    object_side_claim = {
        "claim": INDICATES_CLAIM,
        "role": "object",
    }

    other_predicate_claim = {
        "claim": {
            **INDICATES_CLAIM,
            "claim_id": "CLAIM-002",
            "predicate": "OTHER_RELATION",
        },
        "role": "subject",
    }

    with (
        patch(
            "app.reasoning.symptom_reasoner.get_symptom",
            return_value=SYMPTOM,
        ),
        patch(
            "app.reasoning.symptom_reasoner.get_claims_for_concept",
            return_value=[object_side_claim, other_predicate_claim],
        ),
        patch(
            "app.reasoning.symptom_reasoner.evaluate_claim",
        ) as evaluate_mock,
    ):
        result = reason_about_symptoms(["SYM-001"])

    assert result["results"][0]["indicates_claims"] == []
    assert result["summary"]["indicates_claim_count"] == 0
    evaluate_mock.assert_not_called()


def test_reason_about_symptoms_handles_missing_and_duplicate_ids():
    with (
        patch(
            "app.reasoning.symptom_reasoner.get_symptom",
            return_value=None,
        ) as symptom_mock,
        patch(
            "app.reasoning.symptom_reasoner.get_claims_for_concept",
        ) as claims_mock,
    ):
        result = reason_about_symptoms(
            ["MISSING-SYMPTOM", "MISSING-SYMPTOM"]
        )

    assert result["summary"] == {
        "requested_symptom_count": 2,
        "unique_symptom_count": 1,
        "found_symptom_count": 0,
        "indicates_claim_count": 0,
    }

    assert len(result["results"]) == 1
    assert result["results"][0]["found"] is False

    symptom_mock.assert_called_once_with("MISSING-SYMPTOM", None)
    claims_mock.assert_not_called()


@pytest.mark.parametrize(
    "symptom_ids",
    [
        [],
        ["   "],
        [""],
        ["SYM-001", "   "],
        "SYM-001",
    ],
)
def test_reason_about_symptoms_rejects_invalid_input(symptom_ids):
    with pytest.raises(ValueError):
        reason_about_symptoms(symptom_ids)