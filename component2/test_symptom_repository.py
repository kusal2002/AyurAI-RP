from unittest.mock import MagicMock, patch

import pytest

from app.db import repository
from app.models.symptom import SymptomConcept


@pytest.fixture
def mock_neo4j():
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value

    return driver, session


def test_save_symptom(mock_neo4j):
    driver, session = mock_neo4j

    expected = {
        "symptom_id": "SYM-TEST-001",
        "name": "Synthetic test symptom",
        "aliases": ["Synthetic alias"],
        "description": None,
    }

    session.run.return_value.single.return_value = {
        "symptom": expected
    }

    symptom = SymptomConcept(
        symptom_id="SYM-TEST-001",
        name="Synthetic test symptom",
        aliases=["Synthetic alias"],
    )

    with patch.object(repository, "_get_driver", return_value=driver):
        result = repository.save_symptom(symptom, driver)

    assert result == expected
    session.run.assert_called_once()

    query = session.run.call_args.args[0]
    assert "MERGE (s:Symptom" in query
    assert session.run.call_args.kwargs["symptom_id"] == "SYM-TEST-001"


def test_get_symptom(mock_neo4j):
    driver, session = mock_neo4j

    expected = {
        "symptom_id": "SYM-TEST-001",
        "name": "Synthetic test symptom",
        "aliases": [],
        "description": None,
    }

    session.run.return_value.single.return_value = {
        "symptom": expected
    }

    with patch.object(repository, "_get_driver", return_value=driver):
        result = repository.get_symptom("SYM-TEST-001", driver)

    assert result == expected
    session.run.assert_called_once()


def test_get_symptom_returns_none_when_missing(mock_neo4j):
    driver, session = mock_neo4j
    session.run.return_value.single.return_value = None

    with patch.object(repository, "_get_driver", return_value=driver):
        result = repository.get_symptom("SYM-MISSING", driver)

    assert result is None


@pytest.mark.parametrize("symptom_id", ["", "   "])
def test_get_symptom_rejects_empty_identifier(symptom_id):
    with patch.object(repository, "_get_driver") as get_driver:
        with pytest.raises(ValueError, match="symptom_id must not be empty"):
            repository.get_symptom(symptom_id)

        get_driver.assert_not_called()


def test_save_symptom_raises_when_save_returns_no_record(mock_neo4j):
    driver, session = mock_neo4j
    session.run.return_value.single.return_value = None

    symptom = SymptomConcept(
        symptom_id="SYM-TEST-002",
        name="Another synthetic test symptom",
    )

    with patch.object(repository, "_get_driver", return_value=driver):
        with pytest.raises(RuntimeError, match="Symptom could not be saved"):
            repository.save_symptom(symptom, driver)

@pytest.mark.parametrize(
    "reference",
    [
        "SYM-TEST-001",
        "Synthetic test symptom",
        "synthetic test symptom",
        " Synthetic alias ",
    ],
)
def test_resolve_symptom_reference_returns_unique_match(
    mock_neo4j,
    reference,
):
    driver, session = mock_neo4j

    expected = {
        "symptom_id": "SYM-TEST-001",
        "name": "Synthetic test symptom",
        "aliases": ["Synthetic alias"],
        "description": None,
    }
    session.run.return_value.single.return_value = {
        "symptoms": [expected]
    }

    with patch.object(repository, "_get_driver", return_value=driver):
        result = repository.resolve_symptom_reference(reference, driver)

    assert result["status"] == "resolved"
    assert result["symptom"] == expected
    assert result["candidates"] == [expected]

    kwargs = session.run.call_args.kwargs
    assert kwargs["normalized_reference"] == reference.strip().lower()


def test_resolve_symptom_reference_returns_not_found(mock_neo4j):
    driver, session = mock_neo4j
    session.run.return_value.single.return_value = {"symptoms": []}

    with patch.object(repository, "_get_driver", return_value=driver):
        result = repository.resolve_symptom_reference(
            "unknown symptom",
            driver,
        )

    assert result == {
        "status": "not_found",
        "symptom": None,
        "candidates": [],
    }


def test_resolve_symptom_reference_reports_ambiguity(mock_neo4j):
    driver, session = mock_neo4j

    first = {
        "symptom_id": "SYM-001",
        "name": "Paleness",
        "aliases": ["pallor"],
    }
    second = {
        "symptom_id": "SYM-002",
        "name": "Pallor",
        "aliases": [],
    }
    session.run.return_value.single.return_value = {
        "symptoms": [first, second]
    }

    with patch.object(repository, "_get_driver", return_value=driver):
        result = repository.resolve_symptom_reference("pallor", driver)

    assert result["status"] == "ambiguous"
    assert result["symptom"] is None
    assert result["candidates"] == [first, second]


@pytest.mark.parametrize("reference", ["", "   "])
def test_resolve_symptom_reference_rejects_blank_input(reference):
    with patch.object(repository, "_get_driver") as get_driver:
        with pytest.raises(
            ValueError,
            match="reference must not be empty",
        ):
            repository.resolve_symptom_reference(reference)

        get_driver.assert_not_called()