
from typing import Any

from neo4j import Driver

from app.db.neo4j import get_neo4j_driver
from app.models.claim import Claim
from app.models.evidence import EvidenceRecord
from app.ontology.relationships import validate_relationship
from app.ontology.evidence_validation import validate_evidence_provenance
from app.models.symptom import SymptomConcept



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

def get_concept_type(
    concept_id: str,
    driver: Driver | None = None,
) -> str | None:
    """Return the unique ontology label for a concept ID.

    Returns None when no matching concept exists.
    Raises ValueError when the identifier matches multiple nodes.
    """
    if not concept_id or not concept_id.strip():
        raise ValueError("concept_id must not be empty.")

    db = _get_driver(driver)

    label_conditions = " OR ".join(
        f"(node:{label} AND node.{identifier} = $concept_id)"
        for label, identifier in CONCEPT_IDENTIFIERS.items()
    )

    query = f"""
    MATCH (node)
    WHERE {label_conditions}
    RETURN collect(DISTINCT labels(node)) AS node_labels
    """

    with db.session() as session:
        record = session.run(
            query,
            concept_id=concept_id,
        ).single()

    if record is None:
        return None

    matching_labels = [
        label
        for labels in record["node_labels"]
        for label in labels
        if label in CONCEPT_IDENTIFIERS
    ]

    unique_labels = set(matching_labels)

    if len(unique_labels) > 1:
        raise ValueError(
            f"Concept ID {concept_id!r} matches multiple "
            f"ontology types: {sorted(unique_labels)}"
        )

    return next(iter(unique_labels), None)


def validate_ontology_claim(
    claim: Claim,
    driver: Driver | None = None,
) -> None:
    """Validate a claim against the actual Neo4j concept types."""
    subject_type = get_concept_type(claim.subject_id, driver)
    object_type = get_concept_type(claim.object_id, driver)

    if subject_type is None:
        raise ValueError(
            f"Unknown ontology subject: {claim.subject_id!r}"
        )

    if object_type is None:
        raise ValueError(
            f"Unknown ontology object: {claim.object_id!r}"
        )

    validate_relationship(
        predicate=claim.predicate,
        subject_type=subject_type,
        object_type=object_type,
    )



def _get_driver(driver: Driver | None = None) -> Driver:
    return driver if driver is not None else get_neo4j_driver()


def save_evidence(
    evidence: EvidenceRecord,
    driver: Driver | None = None,
) -> dict[str, Any]:
    """Create or update an evidence record by identifier."""
    validate_evidence_provenance(evidence)

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

def get_claims_for_concept(
    concept_id: str,
    driver: Driver | None = None,
) -> list[dict[str, Any]]:
    """Retrieve claims connected to a concept as subject or object."""
    if not concept_id or not concept_id.strip():
        raise ValueError("concept_id must not be empty.")

    db = _get_driver(driver)

    query = f"""
    MATCH (concept)
    WHERE {
        " OR ".join(
            f"concept:{label} AND concept.{identifier} = $concept_id"
            for label, identifier in CONCEPT_IDENTIFIERS.items()
        )
    }

    MATCH (concept)-[:SUBJECT_OF]->(c:Claim)
    RETURN properties(c) AS claim, 'subject' AS role

    UNION

    MATCH (concept)
    WHERE {
        " OR ".join(
            f"concept:{label} AND concept.{identifier} = $concept_id"
            for label, identifier in CONCEPT_IDENTIFIERS.items()
        )
    }

    MATCH (c:Claim)-[:OBJECT_OF]->(concept)
    RETURN properties(c) AS claim, 'object' AS role
    ORDER BY role
    """

    with db.session() as session:
        records = session.run(
            query,
            concept_id=concept_id,
        )
        return [
            {
                "claim": record["claim"],
                "role": record["role"],
            }
            for record in records
        ]

def get_evidence_for_claim(
    claim_id: str,
    driver: Driver | None = None,
) -> dict[str, Any] | None:
    """Retrieve a claim and its supporting or contradicting evidence."""
    if not claim_id or not claim_id.strip():
        raise ValueError("claim_id must not be empty.")

    db = _get_driver(driver)

    query = """
    MATCH (c:Claim {claim_id: $claim_id})
    OPTIONAL MATCH (e:Evidence)-[r:SUPPORTS|CONTRADICTS]->(c)
    WITH c, [
        item IN collect(
            CASE
                WHEN e IS NULL THEN null
                ELSE {
                    evidence: properties(e),
                    relationship: type(r)
                }
            END
        )
        WHERE item IS NOT NULL
    ] AS evidence_records
    RETURN
        properties(c) AS claim,
        evidence_records
    """

    with db.session() as session:
        record = session.run(
            query,
            claim_id=claim_id,
        ).single()

    if record is None:
        return None

    return {
        "claim": record["claim"],
        "evidence": record["evidence_records"],
    }

def get_connected_knowledge(
    concept_id: str,
    driver: Driver | None = None,
) -> list[dict[str, Any]]:
    """Retrieve connected claims, concepts, and evidence."""
    if not concept_id or not concept_id.strip():
        raise ValueError("concept_id must not be empty.")

    db = _get_driver(driver)

    concept_conditions = " OR ".join(
        f"(concept:{label} AND concept.{identifier} = $concept_id)"
        for label, identifier in CONCEPT_IDENTIFIERS.items()
    )

    query = f"""
    MATCH (concept)
    WHERE {concept_conditions}

    OPTIONAL MATCH (concept)-[:SUBJECT_OF]->(subject_claim:Claim)
    OPTIONAL MATCH (object_claim:Claim)-[:OBJECT_OF]->(concept)

    WITH concept,
         collect(DISTINCT subject_claim) +
         collect(DISTINCT object_claim) AS all_claims

    UNWIND CASE
        WHEN size(all_claims) = 0 THEN [null]
        ELSE all_claims
    END AS claim

    OPTIONAL MATCH (subject)-[:SUBJECT_OF]->(claim)
    OPTIONAL MATCH (claim)-[:OBJECT_OF]->(object)

    WITH concept, claim,
         collect(DISTINCT subject) AS subjects,
         collect(DISTINCT object) AS objects

    OPTIONAL MATCH (supporting:Evidence)-[:SUPPORTS]->(claim)
    WITH concept, claim, subjects, objects,
         collect(DISTINCT properties(supporting)) AS supporting_evidence

    OPTIONAL MATCH (contradicting:Evidence)-[:CONTRADICTS]->(claim)
    WITH concept, claim, subjects, objects, supporting_evidence,
         collect(DISTINCT properties(contradicting)) AS contradicting_evidence

    RETURN
        properties(concept) AS starting_concept,
        properties(claim) AS claim,
        CASE
            WHEN claim IS NULL THEN null
            WHEN concept IN subjects THEN
                head([n IN objects WHERE n <> concept | properties(n)])
            ELSE
                head([n IN subjects WHERE n <> concept | properties(n)])
        END AS related_concept,
        [e IN supporting_evidence WHERE e IS NOT NULL] AS supporting_evidence,
        [e IN contradicting_evidence WHERE e IS NOT NULL] AS contradicting_evidence
    """

    with db.session() as session:
        records = session.run(query, concept_id=concept_id)

        return [
            {
                "starting_concept": record["starting_concept"],
                "claim": record["claim"],
                "related_concept": record["related_concept"],
                "supporting_evidence": record["supporting_evidence"],
                "contradicting_evidence": record["contradicting_evidence"],
            }
            for record in records
        ]

def save_symptom(
    symptom: SymptomConcept,
    driver: Driver | None = None,
) -> dict[str, Any]:
    """Create or update a symptom concept by its stable identifier."""
    db = _get_driver(driver)
    properties = symptom.model_dump()

    query = """
    MERGE (s:Symptom {symptom_id: $symptom_id})
    SET s += $properties
    RETURN properties(s) AS symptom
    """

    with db.session() as session:
        record = session.run(
            query,
            symptom_id=symptom.symptom_id,
            properties=properties,
        ).single()

    if record is None:
        raise RuntimeError("Symptom could not be saved.")

    return record["symptom"]


def get_symptom(
    symptom_id: str,
    driver: Driver | None = None,
) -> dict[str, Any] | None:
    """Retrieve a symptom concept by its identifier."""
    if not symptom_id or not symptom_id.strip():
        raise ValueError("symptom_id must not be empty.")

    db = _get_driver(driver)

    query = """
    MATCH (s:Symptom {symptom_id: $symptom_id})
    RETURN properties(s) AS symptom
    """

    with db.session() as session:
        record = session.run(
            query,
            symptom_id=symptom_id,
        ).single()

    return record["symptom"] if record else None


def get_concepts(
    concept_ids: list[str],
    driver: Driver | None = None,
) -> dict[str, dict[str, Any]]:
    """Retrieve ontology labels and properties for many concept IDs at once.

    Returns a mapping of concept_id -> {"labels": [...], "properties": {...}}.
    IDs with no matching concept are absent from the mapping. When an ID
    matches more than one ontology node, every matching label is returned
    so the caller can treat the concept as ambiguous.
    """
    unique_ids = sorted(
        {
            concept_id.strip()
            for concept_id in concept_ids
            if isinstance(concept_id, str) and concept_id.strip()
        }
    )

    if not unique_ids:
        return {}

    db = _get_driver(driver)

    label_conditions = " OR ".join(
        f"(node:{label} AND node.{identifier} = concept_id)"
        for label, identifier in CONCEPT_IDENTIFIERS.items()
    )

    query = f"""
    UNWIND $concept_ids AS concept_id
    MATCH (node)
    WHERE {label_conditions}
    RETURN concept_id, labels(node) AS node_labels,
           properties(node) AS properties
    """

    concepts: dict[str, dict[str, Any]] = {}

    with db.session() as session:
        for record in session.run(query, concept_ids=unique_ids):
            entry = concepts.setdefault(
                record["concept_id"],
                {"labels": [], "properties": record["properties"]},
            )
            for label in record["node_labels"]:
                if (
                    label in CONCEPT_IDENTIFIERS
                    and label not in entry["labels"]
                ):
                    entry["labels"].append(label)

    return concepts


def list_evidence(
    driver: Driver | None = None,
    limit: int = 10000,
) -> list[dict[str, Any]]:
    """Return stored evidence records ordered by evidence_id."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    db = _get_driver(driver)

    query = """
    MATCH (e:Evidence)
    RETURN properties(e) AS evidence
    ORDER BY e.evidence_id
    LIMIT $limit
    """

    with db.session() as session:
        return [
            record["evidence"]
            for record in session.run(query, limit=limit)
        ]
