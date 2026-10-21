"""Relationship rules for AyurAI Component 2 Ontology v1.1."""

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


# Ontology v1.1 descriptive predicates. They record what a source states
# about a concept (for example a formulation's ingredients) and are kept
# apart from RELATIONSHIP_RULES on purpose: knowledge-chain traversal and
# candidate ranking follow RELATIONSHIP_RULES only, so descriptive claims
# never change reasoning output.
DESCRIPTIVE_RELATIONSHIP_RULES = MappingProxyType(
    {
        "CONTAINS_INGREDIENT": (
            frozenset({"Formulation"}),
            frozenset({"Herb"}),
        ),
    }
)


def validate_relationship(
    predicate: str,
    subject_type: str,
    object_type: str,
    allow_descriptive: bool = False,
) -> None:
    """Validate a domain relationship against Ontology v1.1.

    Descriptive predicates are accepted only when allow_descriptive is
    True; existing callers keep the v1.0 reasoning predicates only.

    Raises:
        ValueError: If the predicate is unknown or the node types
            are not permitted for that predicate.
    """
    rules = (
        {**RELATIONSHIP_RULES, **DESCRIPTIVE_RELATIONSHIP_RULES}
        if allow_descriptive
        else RELATIONSHIP_RULES
    )
    if predicate not in rules:
        raise ValueError(
            f"Unsupported ontology predicate: {predicate!r}"
        )

    allowed_subjects, allowed_objects = rules[predicate]

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
