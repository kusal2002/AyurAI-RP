"""Service for validating and saving ontology domain claims."""

from typing import Any

from neo4j import Driver

from app.db.repository import save_claim, validate_ontology_claim
from app.models.claim import Claim


def save_ontology_claim(
    claim: Claim,
    driver: Driver | None = None,
) -> dict[str, Any]:
    """Validate a domain claim against the ontology before saving.

    Generic repository claims remain supported through save_claim().
    This service only accepts predicates defined in the ontology.
    """
    validate_ontology_claim(claim, driver)
    return save_claim(claim, driver)
