"""Service for validating and saving ontology domain claims."""
from typing import Any

from neo4j import Driver

from app.db.repository import (
    link_evidence_to_claim,
    save_claim,
    validate_ontology_claim,
)
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


def save_claim_with_evidence(
    claim: Claim,
    evidence_links: list[tuple[str, str]],
    driver: Driver | None = None,
) -> dict[str, Any]:
    """Save an ontology claim and link its supporting or contradicting evidence.

    Each evidence link is a tuple of (evidence_id, relationship),
    where relationship must be SUPPORTS or CONTRADICTS.

    The claim is saved before evidence links are created. If linking
    fails, the saved claim remains in the database.
    """
    for evidence_id, relationship in evidence_links:
        if not evidence_id or not evidence_id.strip():
            raise ValueError("evidence_id must not be empty.")

        if relationship not in {"SUPPORTS", "CONTRADICTS"}:
            raise ValueError(
                "relationship must be SUPPORTS or CONTRADICTS"
            )

    saved_claim = save_ontology_claim(claim, driver)

    linked_evidence = []

    for evidence_id, relationship in evidence_links:
        link_evidence_to_claim(
            evidence_id,
            claim.claim_id,
            relationship,
            driver,
        )
        linked_evidence.append(
            {
                "evidence_id": evidence_id,
                "relationship": relationship,
            }
        )

    return {
        "claim": saved_claim,
        "evidence_links": linked_evidence,
    }