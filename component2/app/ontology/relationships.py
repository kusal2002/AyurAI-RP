"""Relationship rules for AyurAI Component 2 Ontology v1.0."""

from types import MappingProxyType


# Maps each domain predicate to its permitted source and target node types.
# These rules are based on docs/ontology_v1.md.
RELATIONSHIP_RULES = MappingProxyType(
    {
        "INDICATES": (frozenset({"Symptom"}), frozenset({"Roga"})),
        "ASSOCIATED_WITH_DOSHA": (
            frozenset({"Roga"}),
            frozenset({"Dosha"}),
        ),
        "AFFECTS_DHATU": (
            frozenset({"Roga"}),
            frozenset({"Dhatu"}),
        ),
        "SUGGESTS_PRINCIPLE": (
            frozenset({"Roga", "Dosha", "Dhatu"}),
            frozenset({"TherapeuticPrinciple"}),
        ),
        "USES_HERB": (
            frozenset({"TherapeuticPrinciple"}),
            frozenset({"Herb"}),
        ),
        "USES_FORMULATION": (
            frozenset({"TherapeuticPrinciple"}),
            frozenset({"Formulation"}),
        ),
        "RECOMMENDS_DIET": (
            frozenset({"TherapeuticPrinciple"}),
            frozenset({"Diet"}),
        ),
        "RECOMMENDS_LIFESTYLE": (
            frozenset({"TherapeuticPrinciple"}),
            frozenset({"Lifestyle"}),
        ),
    }
)


def validate_relationship(
    predicate: str,
    subject_type: str,
    object_type: str,
) -> None:
    """Validate a domain relationship against Ontology v1.0.

    Raises:
        ValueError: If the predicate is unknown or the node types
            are not permitted for that predicate.
    """
    if predicate not in RELATIONSHIP_RULES:
        raise ValueError(
            f"Unsupported ontology predicate: {predicate!r}"
        )

    allowed_subjects, allowed_objects = RELATIONSHIP_RULES[predicate]

    if subject_type not in allowed_subjects:
        raise ValueError(
            f"{predicate} does not allow subject type "
            f"{subject_type!r}. Allowed: {sorted(allowed_subjects)}"
        )

    if object_type not in allowed_objects:
        raise ValueError(
            f"{predicate} does not allow object type "
            f"{object_type!r}. Allowed: {sorted(allowed_objects)}"
        )
