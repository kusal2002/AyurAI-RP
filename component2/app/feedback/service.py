"""Storage and query refinement for practitioner feedback.

Feedback is stored as an append-only PractitionerFeedback node. REVIEWS
relationships point from the feedback to existing Claim nodes so the
review is traceable, but claims and their verification status are never
modified here.
"""

import json
from typing import Any

from neo4j import Driver

from app.db.neo4j import get_neo4j_driver
from app.db.repository import get_concepts
from app.models.feedback import PractitionerFeedback, RefinementQuery


class DuplicateFeedbackError(ValueError):
    """Raised when a feedback_id already exists (feedback is append-only)."""


def save_feedback(
    feedback: PractitionerFeedback,
    driver: Driver | None = None,
) -> dict[str, Any]:
    db = driver if driver is not None else get_neo4j_driver()
    properties = feedback.model_dump(mode="json")

    query = """
    OPTIONAL MATCH (existing:PractitionerFeedback {feedback_id: $feedback_id})
    WITH existing
    WHERE existing IS NULL
    CREATE (f:PractitionerFeedback)
    SET f = $properties
    WITH f
    OPTIONAL MATCH (c:Claim)
    WHERE c.claim_id IN $claim_ids
    FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
        MERGE (f)-[:REVIEWS]->(c)
    )
    RETURN f.feedback_id AS feedback_id,
           collect(c.claim_id) AS linked_claim_ids
    """

    with db.session() as session:
        record = session.run(
            query,
            feedback_id=feedback.feedback_id,
            properties=properties,
            claim_ids=feedback.claim_ids,
        ).single()

    if record is None:
        raise DuplicateFeedbackError(
            f"Feedback {feedback.feedback_id!r} already exists."
        )

    linked = sorted(record["linked_claim_ids"])
    return {
        "feedback_id": record["feedback_id"],
        "linked_claim_ids": linked,
        "unknown_claim_ids": sorted(set(feedback.claim_ids) - set(linked)),
    }


def get_feedback(
    feedback_id: str,
    driver: Driver | None = None,
) -> dict[str, Any] | None:
    db = driver if driver is not None else get_neo4j_driver()
    with db.session() as session:
        record = session.run(
            """
            MATCH (f:PractitionerFeedback {feedback_id: $feedback_id})
            OPTIONAL MATCH (f)-[:REVIEWS]->(c:Claim)
            RETURN properties(f) AS feedback,
                   collect(c.claim_id) AS reviewed_claim_ids
            """,
            feedback_id=feedback_id,
        ).single()
    if record is None:
        return None
    return {
        "feedback": record["feedback"],
        "reviewed_claim_ids": sorted(record["reviewed_claim_ids"]),
    }


def build_refinement_query(
    feedback: PractitionerFeedback,
    concepts: dict[str, dict[str, Any]],
) -> RefinementQuery:
    """Build an explicit retrieval query from feedback terms and the
    stored names of suggested concepts."""
    names = []
    unknown = []
    for concept_id in feedback.suggested_concept_ids:
        entry = concepts.get(concept_id)
        if entry is None:
            unknown.append(concept_id)
            continue
        name = (entry.get("properties") or {}).get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())

    terms = list(feedback.refinement_terms)
    for name in names:
        if name.casefold() not in {t.casefold() for t in terms}:
            terms.append(name)

    return RefinementQuery(
        feedback_id=feedback.feedback_id,
        query_text=" ; ".join(terms) if terms else None,
        terms=terms,
        concept_ids=[
            c for c in feedback.suggested_concept_ids if c not in unknown
        ],
        unknown_concept_ids=unknown,
    )


def build_refinement_query_from_store(
    feedback: PractitionerFeedback,
    driver: Driver | None = None,
) -> RefinementQuery:
    concepts = (
        get_concepts(feedback.suggested_concept_ids, driver)
        if feedback.suggested_concept_ids
        else {}
    )
    return build_refinement_query(feedback, concepts)


def feedback_audit_summary(feedback: PractitionerFeedback) -> str:
    """Safe audit line: identifiers and categories only, no rationale."""
    return json.dumps(
        {
            "event": "c2.feedback.recorded",
            "feedback_id": feedback.feedback_id,
            "request_id": feedback.request_id,
            "claim_ids": feedback.claim_ids,
            "candidate_ids": feedback.candidate_ids,
            "evidence_ids": feedback.evidence_ids,
            "review_outcome": feedback.review_outcome.value,
            "issue_category": feedback.issue_category.value,
            "reviewer_role": feedback.reviewer_role.value,
            "created_at": feedback.created_at.isoformat(),
        },
        sort_keys=True,
    )
