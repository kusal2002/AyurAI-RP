from unittest.mock import Mock, patch

import pytest

from app.models.claim import Claim
from app.ontology.claim_service import save_ontology_claim


def make_claim(
    predicate="INDICATES",
    subject_id="SYM-001",
    object_id="ROGA-001",
):
    return Claim(
        claim_id="TEST-SERVICE-CLAIM",
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        statement="Synthetic claim for service testing.",
    )


@patch("app.ontology.claim_service.save_claim")
@patch("app.ontology.claim_service.validate_ontology_claim")
def test_valid_claim_is_validated_then_saved(
    validate_mock,
    save_mock,
):
    claim = make_claim()
    save_mock.return_value = {"claim_id": claim.claim_id}
    driver = Mock()

    result = save_ontology_claim(claim, driver)

    validate_mock.assert_called_once_with(claim, driver)
    save_mock.assert_called_once_with(claim, driver)
    assert result["claim_id"] == claim.claim_id


@patch("app.ontology.claim_service.save_claim")
@patch("app.ontology.claim_service.validate_ontology_claim")
def test_invalid_claim_is_not_saved(
    validate_mock,
    save_mock,
):
    claim = make_claim(predicate="UNKNOWN_RELATION")
    validate_mock.side_effect = ValueError("Unsupported predicate")

    with pytest.raises(ValueError, match="Unsupported predicate"):
        save_ontology_claim(claim)

    save_mock.assert_not_called()


@patch("app.ontology.claim_service.save_claim")
@patch("app.ontology.claim_service.validate_ontology_claim")
def test_save_error_is_propagated(
    validate_mock,
    save_mock,
):
    claim = make_claim()
    save_mock.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError, match="Database failure"):
        save_ontology_claim(claim)

    validate_mock.assert_called_once_with(claim, None)
