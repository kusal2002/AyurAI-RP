from unittest.mock import patch

import pytest

from app.reasoning.evaluator import evaluate_claim


CLAIM = {
    "claim_id": "TEST-CLAIM",
    "statement": "Example research claim",
    "confidence": 0.7,
    "verification_status": "unverified",
}

SUPPORTING_EVIDENCE = {
    "evidence_id": "TEST-EVIDENCE-1",
    "title": "Supporting source",
    "source_name": "Test publication",
    "evidence_type": "modern_research",
    "section": "Section 1",
    "page": "10",
    "citation": "Test citation",
    "source_url": "https://example.org/source",
    "practitioner_verified": False,
}

CONTRADICTING_EVIDENCE = {
    "evidence_id": "TEST-EVIDENCE-2",
    "title": "Contradicting source",
    "source_name": "Another publication",
    "evidence_type": "classical",
    "section": "Chapter 2",
    "page": "20",
    "citation": "Another citation",
    "source_url": None,
    "practitioner_verified": False,
}


def test_evaluate_claim_separates_evidence():
    repository_result = {
        "claim": CLAIM,
        "evidence": [
            {
                "evidence": SUPPORTING_EVIDENCE,
                "relationship": "SUPPORTS",
            },
            {
                "evidence": CONTRADICTING_EVIDENCE,
                "relationship": "CONTRADICTS",
            },
        ],
    }

    with patch(
        "app.reasoning.evaluator.get_evidence_for_claim",
        return_value=repository_result,
    ):
        result = evaluate_claim("TEST-CLAIM")

    assert result is not None
    assert result["verification_status"] == "unverified"
    assert result["stored_confidence"] == 0.7
    assert len(result["supporting_evidence"]) == 1
    assert len(result["contradicting_evidence"]) == 1
    assert result["supporting_evidence"][0]["evidence_id"] == (
        "TEST-EVIDENCE-1"
    )
    assert result["contradicting_evidence"][0]["evidence_id"] == (
        "TEST-EVIDENCE-2"
    )
    assert result["evidence_summary"] == {
        "supporting_count": 1,
        "contradicting_count": 1,
    }
    assert result["medical_conclusion"] is None


def test_evaluate_claim_without_evidence():
    with patch(
        "app.reasoning.evaluator.get_evidence_for_claim",
        return_value={"claim": CLAIM, "evidence": []},
    ):
        result = evaluate_claim("TEST-CLAIM")

    assert result is not None
    assert result["supporting_evidence"] == []
    assert result["contradicting_evidence"] == []
    assert result["evidence_summary"] == {
        "supporting_count": 0,
        "contradicting_count": 0,
    }
    assert any(
        "No supporting evidence" in note
        for note in result["reasoning_notes"]
    )


def test_evaluate_missing_claim():
    with patch(
        "app.reasoning.evaluator.get_evidence_for_claim",
        return_value=None,
    ):
        result = evaluate_claim("MISSING-CLAIM")

    assert result is None


def test_evaluate_disputed_claim():
    disputed_claim = {
        **CLAIM,
        "verification_status": "disputed",
    }

    with patch(
        "app.reasoning.evaluator.get_evidence_for_claim",
        return_value={"claim": disputed_claim, "evidence": []},
    ):
        result = evaluate_claim("TEST-CLAIM")

    assert result is not None
    assert result["verification_status"] == "disputed"
    assert any(
        "disputed" in note.lower()
        for note in result["reasoning_notes"]
    )


def test_reject_empty_claim_id():
    with pytest.raises(ValueError, match="claim_id must not be empty"):
        evaluate_claim("   ")

def test_reject_unsupported_evidence_relationship():
    repository_result = {
        "claim": CLAIM,
        "evidence": [
            {
                "evidence": SUPPORTING_EVIDENCE,
                "relationship": "UNKNOWN",
            }
        ],
    }

    with patch(
        "app.reasoning.evaluator.get_evidence_for_claim",
        return_value=repository_result,
    ):
        with pytest.raises(
            ValueError,
            match="Unsupported evidence relationship",
        ):
            evaluate_claim("TEST-CLAIM")


def test_evaluate_claim_warns_when_evidence_conflicts():
    repository_result = {
        "claim": CLAIM,
        "evidence": [
            {
                "evidence": SUPPORTING_EVIDENCE,
                "relationship": "SUPPORTS",
            },
            {
                "evidence": CONTRADICTING_EVIDENCE,
                "relationship": "CONTRADICTS",
            },
        ],
    }

    with patch(
        "app.reasoning.evaluator.get_evidence_for_claim",
        return_value=repository_result,
    ):
        result = evaluate_claim("TEST-CLAIM")

    assert result is not None
    assert result["verification_status"] == "unverified"
    assert result["stored_confidence"] == 0.7
    assert result["evidence_summary"] == {
        "supporting_count": 1,
        "contradicting_count": 1,
    }
    assert any(
        "Conflicting evidence is present" in note
        for note in result["reasoning_notes"]
    )
    assert result["medical_conclusion"] is None
