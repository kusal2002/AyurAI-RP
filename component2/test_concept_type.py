import pytest

from app.db.repository import get_concept_type


class FakeResult:
    def __init__(self, record):
        self.record = record

    def single(self):
        return self.record


class FakeSession:
    def __init__(self, record):
        self.record = record
        self.query = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def run(self, query, **parameters):
        self.query = query
        self.parameters = parameters
        return FakeResult(self.record)


class FakeDriver:
    def __init__(self, record):
        self.session_instance = FakeSession(record)

    def session(self):
        return self.session_instance


def test_get_concept_type_returns_label():
    driver = FakeDriver(
        {"node_labels": [["Symptom"]]}
    )

    result = get_concept_type("SYM-001", driver)

    assert result == "Symptom"
    assert driver.session_instance.parameters == {
        "concept_id": "SYM-001"
    }


def test_get_concept_type_returns_none_when_missing():
    driver = FakeDriver({"node_labels": []})

    result = get_concept_type("MISSING-001", driver)

    assert result is None


def test_get_concept_type_rejects_multiple_types():
    driver = FakeDriver(
        {"node_labels": [["Symptom"], ["Roga"]]}
    )

    with pytest.raises(ValueError, match="multiple ontology types"):
        get_concept_type("DUPLICATE-001", driver)


@pytest.mark.parametrize("concept_id", ["", "   "])
def test_get_concept_type_rejects_empty_identifier(concept_id):
    with pytest.raises(ValueError, match="must not be empty"):
        get_concept_type(concept_id, FakeDriver(None))


from unittest.mock import patch

from app.db.repository import validate_ontology_claim
from app.models.claim import Claim


def make_claim(
    subject_id="SYM-001",
    predicate="INDICATES",
    object_id="ROGA-001",
):
    return Claim(
        claim_id="TEST-ONTOLOGY-CLAIM",
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        statement="Synthetic test claim.",
    )


def test_validate_ontology_claim_accepts_valid_types():
    claim = make_claim()

    with (
        patch(
            "app.db.repository.get_concept_type",
            side_effect=["Symptom", "Roga"],
        ),
        patch(
            "app.db.repository.validate_relationship"
        ) as validate_relationship_mock,
    ):
        validate_ontology_claim(claim)

    validate_relationship_mock.assert_called_once_with(
        predicate="INDICATES",
        subject_type="Symptom",
        object_type="Roga",
    )


def test_validate_ontology_claim_rejects_missing_subject():
    claim = make_claim()

    with patch(
        "app.db.repository.get_concept_type",
        side_effect=[None, "Roga"],
    ):
        with pytest.raises(ValueError, match="Unknown ontology subject"):
            validate_ontology_claim(claim)


def test_validate_ontology_claim_rejects_missing_object():
    claim = make_claim()

    with patch(
        "app.db.repository.get_concept_type",
        side_effect=["Symptom", None],
    ):
        with pytest.raises(ValueError, match="Unknown ontology object"):
            validate_ontology_claim(claim)


def test_validate_ontology_claim_propagates_invalid_relationship():
    claim = make_claim(
        predicate="INDICATES",
        subject_id="ROGA-001",
        object_id="SYM-001",
    )

    with (
        patch(
            "app.db.repository.get_concept_type",
            side_effect=["Roga", "Symptom"],
        ),
        patch(
            "app.db.repository.validate_relationship",
            side_effect=ValueError("Invalid relationship"),
        ),
    ):
        with pytest.raises(ValueError, match="Invalid relationship"):
            validate_ontology_claim(claim)
