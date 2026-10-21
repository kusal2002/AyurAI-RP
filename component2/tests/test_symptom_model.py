import pytest
from pydantic import ValidationError

from app.models.symptom import SymptomConcept


def test_accepts_valid_symptom():
    symptom = SymptomConcept(
        symptom_id="SYM-001",
        name="Example symptom",
        aliases=["Example alias"],
    )

    assert symptom.symptom_id == "SYM-001"
    assert symptom.name == "Example symptom"
    assert symptom.aliases == ["Example alias"]


def test_trims_required_text():
    symptom = SymptomConcept(
        symptom_id=" SYM-001 ",
        name=" Example symptom ",
    )

    assert symptom.symptom_id == "SYM-001"
    assert symptom.name == "Example symptom"



@pytest.mark.parametrize(
    "field",
    ["symptom_id", "name"],
)
def test_rejects_blank_required_text(field):
    data = {
        "symptom_id": "SYM-001",
        "name": "Example symptom",
    }
    data[field] = "   "

    with pytest.raises(ValidationError):
        SymptomConcept(**data)



def test_aliases_default_to_empty_list():
    symptom = SymptomConcept(
        symptom_id="SYM-001",
        name="Example symptom",
    )

    assert symptom.aliases == []


def test_aliases_are_deduplicated_case_insensitively():
    symptom = SymptomConcept(
        symptom_id="SYM-001",
        name="Example symptom",
        aliases=["Example alias", " example alias ", "Another alias"],
    )

    assert symptom.aliases == ["Example alias", "Another alias"]


def test_rejects_blank_alias():
    with pytest.raises(ValidationError):
        SymptomConcept(
            symptom_id="SYM-001",
            name="Example symptom",
            aliases=["   "],
        )
