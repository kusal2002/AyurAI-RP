import pytest

from app.ontology.relationships import validate_relationship


@pytest.mark.parametrize(
    ("predicate", "subject_type", "object_type"),
    [
        ("INDICATES", "Symptom", "Roga"),
        ("ASSOCIATED_WITH_DOSHA", "Roga", "Dosha"),
        ("AFFECTS_DHATU", "Roga", "Dhatu"),
        ("SUGGESTS_PRINCIPLE", "Roga", "TherapeuticPrinciple"),
        ("SUGGESTS_PRINCIPLE", "Dosha", "TherapeuticPrinciple"),
        ("SUGGESTS_PRINCIPLE", "Dhatu", "TherapeuticPrinciple"),
        ("USES_HERB", "TherapeuticPrinciple", "Herb"),
        ("USES_FORMULATION", "TherapeuticPrinciple", "Formulation"),
        ("RECOMMENDS_DIET", "TherapeuticPrinciple", "Diet"),
        ("RECOMMENDS_LIFESTYLE", "TherapeuticPrinciple", "Lifestyle"),
    ],
)
def test_valid_relationships(
    predicate, subject_type, object_type
):
    validate_relationship(predicate, subject_type, object_type)


@pytest.mark.parametrize(
    ("predicate", "subject_type", "object_type"),
    [
        ("INDICATES", "Roga", "Symptom"),
        ("USES_HERB", "Herb", "TherapeuticPrinciple"),
        ("AFFECTS_DHATU", "Symptom", "Dhatu"),
        ("RECOMMENDS_DIET", "TherapeuticPrinciple", "Herb"),
        ("UNKNOWN_RELATION", "Symptom", "Roga"),
        ("SUPPORTS", "Evidence", "Claim"),
    ],
)
def test_invalid_relationships(
    predicate, subject_type, object_type
):
    with pytest.raises(ValueError):
        validate_relationship(predicate, subject_type, object_type)
