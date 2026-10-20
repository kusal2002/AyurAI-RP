"""Read functions for the research scope: approved AND provisional knowledge.

Used only when a request explicitly asks for
`knowledge_scope=approved_and_provisional`. The approved-only functions in
app/db/repository.py are unchanged and never see provisional records.

Each claim dict gets `knowledge_status`: "approved" for `:Claim` nodes
(which do not store the property) and "provisional" for
`:ProvisionalClaim` nodes. Evidence dicts likewise. Shapes match the
approved functions so the reasoning code is shared.
"""

from typing import Any

from neo4j import Driver

from app.db.repository import CONCEPT_IDENTIFIERS, _get_driver, get_concepts, get_symptom

_CONCEPT_MATCH = " OR ".join(
    f"(concept:{label} AND concept.{identifier} = $concept_id)"
    for label, identifier in CONCEPT_IDENTIFIERS.items()
)

_CLAIMS_FOR_CONCEPT = f"""
MATCH (concept) WHERE {_CONCEPT_MATCH}
CALL {{
  WITH concept
  MATCH (concept)-[:SUBJECT_OF]->(c:Claim) RETURN c, 'subject' AS role, 'approved' AS ks
  UNION
  WITH concept
  MATCH (c:Claim)-[:OBJECT_OF]->(concept) RETURN c, 'object' AS role, 'approved' AS ks
  UNION
  WITH concept
  MATCH (concept)-[:PROVISIONAL_SUBJECT_OF]->(c:ProvisionalClaim) RETURN c, 'subject' AS role, 'provisional' AS ks
  UNION
  WITH concept
  MATCH (c:ProvisionalClaim)-[:PROVISIONAL_OBJECT_OF]->(concept) RETURN c, 'object' AS role, 'provisional' AS ks
}}
RETURN properties(c) AS claim, role, ks,
  [(e)-[:SUPPORTS]->(c) WHERE e:Evidence | properties(e)]
  + [(e)-[:PROVISIONALLY_SUPPORTS]->(c) WHERE e:ProvisionalEvidence | properties(e)] AS supporting_evidence,
  [(e)-[:CONTRADICTS]->(c) WHERE e:Evidence | properties(e)] AS contradicting_evidence,
  [(e)-[:PROVISIONALLY_QUALIFIES]->(c) WHERE e:ProvisionalEvidence | properties(e)] AS qualifying_evidence
ORDER BY role, claim.claim_id
"""


def _tag(items: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    tagged = []
    for item in items:
        item = dict(item)
        item.setdefault("knowledge_status", status)
        tagged.append(item)
    return tagged


def _claim_rows(concept_id: str, driver: Driver | None) -> list[dict[str, Any]]:
    if not concept_id or not concept_id.strip():
        raise ValueError("concept_id must not be empty.")
    db = _get_driver(driver)
    with db.session() as session:
        rows = []
        for record in session.run(_CLAIMS_FOR_CONCEPT, concept_id=concept_id):
            status = record["ks"]
            claim = dict(record["claim"])
            claim.setdefault("knowledge_status", status)
            rows.append({
                "claim": claim,
                "role": record["role"],
                "supporting_evidence": _tag(record["supporting_evidence"], status),
                "contradicting_evidence": _tag(record["contradicting_evidence"], status),
                "qualifying_evidence": _tag(record["qualifying_evidence"], "provisional"),
            })
        return rows


class ResearchGraphAccess:
    """Graph reads over approved + provisional knowledge (one object per request)."""

    knowledge_scope = "approved_and_provisional"

    def __init__(self, driver: Driver | None = None):
        self.driver = driver

    def get_symptom(self, symptom_id, driver=None):
        return get_symptom(symptom_id, driver or self.driver)

    def get_concepts(self, concept_ids, driver=None):
        return get_concepts(concept_ids, driver or self.driver)

    def get_claims_for_concept(self, concept_id, driver=None):
        return [{"claim": r["claim"], "role": r["role"]} for r in _claim_rows(concept_id, driver or self.driver)]

    def get_connected_knowledge(self, concept_id, driver=None):
        return [
            {key: row[key] for key in ("claim", "supporting_evidence", "contradicting_evidence", "qualifying_evidence")}
            for row in _claim_rows(concept_id, driver or self.driver)
        ]

    def get_evidence_for_claim(self, claim_id, driver=None):
        db = _get_driver(driver or self.driver)
        query = """
        MATCH (c) WHERE (c:Claim OR c:ProvisionalClaim) AND c.claim_id = $claim_id
        RETURN properties(c) AS claim, c:ProvisionalClaim AS provisional,
          [(e)-[:SUPPORTS]->(c) WHERE e:Evidence | {evidence: properties(e), relationship: 'SUPPORTS'}]
          + [(e)-[:CONTRADICTS]->(c) WHERE e:Evidence | {evidence: properties(e), relationship: 'CONTRADICTS'}]
          + [(e)-[:PROVISIONALLY_SUPPORTS]->(c) WHERE e:ProvisionalEvidence | {evidence: properties(e), relationship: 'SUPPORTS'}]
          AS evidence
        """
        with db.session() as session:
            record = session.run(query, claim_id=claim_id).single()
        if record is None:
            return None
        status = "provisional" if record["provisional"] else "approved"
        claim = dict(record["claim"])
        claim.setdefault("knowledge_status", status)
        return {
            "claim": claim,
            "evidence": [
                {"evidence": {**item["evidence"], "knowledge_status": item["evidence"].get("knowledge_status", status)},
                 "relationship": item["relationship"]}
                for item in record["evidence"]
            ],
        }


def list_research_evidence(driver: Driver | None = None, limit: int = 10000) -> list[dict[str, Any]]:
    """Approved :Evidence plus :ProvisionalEvidence (for the research index)."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer.")
    db = _get_driver(driver)
    query = """
    MATCH (e) WHERE e:Evidence OR e:ProvisionalEvidence
    RETURN properties(e) AS evidence, e:ProvisionalEvidence AS provisional
    ORDER BY e.evidence_id
    LIMIT $limit
    """
    with db.session() as session:
        return [
            {**record["evidence"],
             "knowledge_status": record["evidence"].get(
                 "knowledge_status", "provisional" if record["provisional"] else "approved")}
            for record in session.run(query, limit=limit)
        ]


def list_provisional_knowledge(driver: Driver | None = None, category: str | None = None,
                               limit: int = 200) -> list[dict[str, Any]]:
    """Provisional claims with their evidence, for the research knowledge view."""
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500.")
    db = _get_driver(driver)
    query = """
    MATCH (s)-[:PROVISIONAL_SUBJECT_OF]->(c:ProvisionalClaim)-[:PROVISIONAL_OBJECT_OF]->(o)
    WHERE $category IS NULL OR c.claim_category = $category
    RETURN properties(c) AS claim,
      coalesce(s.name, c.subject_id) AS subject_name, labels(s)[0] AS subject_type,
      coalesce(o.name, c.object_id) AS object_name, labels(o)[0] AS object_type,
      [(e)-[:PROVISIONALLY_SUPPORTS]->(c) | properties(e)] AS evidence,
      [(e)-[:PROVISIONALLY_QUALIFIES]->(c) | properties(e)] AS qualifying_evidence
    ORDER BY c.claim_category, c.claim_key
    LIMIT $limit
    """
    with db.session() as session:
        return [record.data() for record in session.run(query, category=category, limit=limit)]


def list_reference_evidence(driver: Driver | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Modern reference statements (provisional evidence not tied to claims)."""
    db = _get_driver(driver)
    query = """
    MATCH (e:ProvisionalEvidence {evidence_role: 'modern_reference'})
    RETURN properties(e) AS evidence ORDER BY e.category, e.evidence_id LIMIT $limit
    """
    with db.session() as session:
        return [record["evidence"] for record in session.run(query, limit=limit)]
