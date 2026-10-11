
from typing import Any

from neo4j import Driver

from app.db.neo4j import get_neo4j_driver
from app.models.claim import Claim
from app.models.evidence import EvidenceRecord


# Only these ontology labels and identifier properties are accepted.
CONCEPT_IDENTIFIERS = {
    "Symptom": "symptom_id",
    "Roga": "roga_id",
    "Dosha": "dosha_id",
    "Dhatu": "dhatu_id",
    "TherapeuticPrinciple": "principle_id",
    "Herb": "herb_id",
    "Formulation": "formulation_id",
    "Diet": "diet_id",
    "Lifestyle": "lifestyle_id",
}

IDENTIFIER_EXPRESSION = """
coalesce(
    node.symptom_id,
    node.roga_id,
    node.dosha_id,
    node.dhatu_id,
    node.principle_id,
    node.herb_id,
    node.formulation_id,
    node.diet_id,
    node.lifestyle_id
)
"""


def _get_driver(driver: Driver | None = None) -> Driver:
    return driver if driver is not None else get_neo4j_driver()


def save_evidence(
    evidence: EvidenceRecord,
    driver: Driver | None = None,
) -> dict[str, Any]:
    """Create or update an evidence record by identifier."""
    db = _get_driver(driver)
    properties = evidence.model_dump(mode="json")

    query = """
    MERGE (e:Evidence {evidence_id: $evidence_id})
    SET e += $properties
    RETURN properties(e) AS evidence
    """

    with db.session() as session:
        record = session.run(
            query,
            evidence_id=evidence.evidence_id,
            properties=properties,
        ).single()

    if record is None:
        raise RuntimeError("Evidence could not be saved.")

    return record["evidence"]


def get_evidence(
    evidence_id: str,
    driver: Driver | None = None,
) -> dict[str, Any] | None:
    """Retrieve evidence by identifier."""
    db = _get_driver(driver)

    query = """
    MATCH (e:Evidence {evidence_id: $evidence_id})
    RETURN properties(e) AS evidence
    """

    with db.session() as session:
        record = session.run(
            query, evidence_id=evidence_id
        ).single()

    return record["evidence"] if record else None





def save_claim(
    claim: Claim,
    driver: Driver | None = None,
) -> dict[str, Any]:
    """Save a claim and replace its subject/object relationships."""
    db = _get_driver(driver)
    properties = claim.model_dump(mode="json")

    subject_conditions = " OR ".join(
        f"(subject:{label} AND subject.{identifier} = $subject_id)"
        for label, identifier in CONCEPT_IDENTIFIERS.items()
    )
    object_conditions = " OR ".join(
        f"(object:{label} AND object.{identifier} = $object_id)"
        for label, identifier in CONCEPT_IDENTIFIERS.items()
    )

    query = f"""
    MATCH (subject)
    WHERE {subject_conditions}
    MATCH (object)
    WHERE {object_conditions}

    WITH collect(DISTINCT subject) AS subjects,
         collect(DISTINCT object) AS objects
    WHERE size(subjects) = 1 AND size(objects) = 1

    WITH subjects[0] AS subject, objects[0] AS object
    MERGE (c:Claim {{claim_id: $claim_id}})
    SET c += $properties

    WITH subject, object, c
    OPTIONAL MATCH ()-[old_subject:SUBJECT_OF]->(c)
    WITH subject, object, c, collect(old_subject) AS old_subjects
    FOREACH (r IN old_subjects | DELETE r)

    WITH subject, object, c
    OPTIONAL MATCH (c)-[old_object:OBJECT_OF]->()
    WITH subject, object, c, collect(old_object) AS old_objects
    FOREACH (r IN old_objects | DELETE r)

    WITH subject, object, c
    MERGE (subject)-[:SUBJECT_OF]->(c)
    MERGE (c)-[:OBJECT_OF]->(object)

    RETURN properties(c) AS claim
    """


    with db.session() as session:
        record = session.run(
            query,
            subject_id=claim.subject_id,
            object_id=claim.object_id,
            claim_id=claim.claim_id,
        properties=properties,
    ).single()


    if record is None:
        raise ValueError(
            "Claim subject or object was not found uniquely."
        )

    return record["claim"]



def get_claim(
    claim_id: str,
    driver: Driver | None = None,
) -> dict[str, Any] | None:
    """Retrieve a claim by identifier."""
    db = _get_driver(driver)

    query = """
    MATCH (c:Claim {claim_id: $claim_id})
    RETURN properties(c) AS claim
    """

    with db.session() as session:
        record = session.run(
            query, claim_id=claim_id
        ).single()

    return record["claim"] if record else None


def link_evidence_to_claim(
    evidence_id: str,
    claim_id: str,
    relationship: str,
    driver: Driver | None = None,
) -> None:
    """
    Link existing evidence to an existing claim.

    relationship must be SUPPORTS or CONTRADICTS.
    """
    if relationship not in {"SUPPORTS", "CONTRADICTS"}:
        raise ValueError(
            "relationship must be SUPPORTS or CONTRADICTS"
        )

    db = _get_driver(driver)

    query = f"""
    MATCH (e:Evidence {{evidence_id: $evidence_id}})
    MATCH (c:Claim {{claim_id: $claim_id}})
    MERGE (e)-[:{relationship}]->(c)
    RETURN e.evidence_id AS evidence_id
    """

    with db.session() as session:
        record = session.run(
            query,
            evidence_id=evidence_id,
            claim_id=claim_id,
        ).single()

    if record is None:
        raise ValueError(
            "Evidence or claim does not exist. Save both first."
        )
