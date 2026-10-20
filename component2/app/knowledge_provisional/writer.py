"""Write and verify a provisional plan in Neo4j (idempotent, additive only).

- Every statement is a MERGE on a deterministic ID; re-running the same
  plan creates nothing new (counters report 0 nodes/relationships).
- Each claim (with its sources, chunks, concepts and evidence) and each
  reference statement is one write transaction; a failure rolls back that
  item only and stops the run with a clear error.
- Existing concept nodes are matched, never modified (ON CREATE only).
  Existing Source nodes with different content abort the item (Stage E
  source-hash guard, reused).
- Nothing is deleted. No `:Claim` or `:Evidence` node is ever created.
- Labels and relationship types come from fixed strings in this module.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from neo4j import READ_ACCESS, Driver, unit_of_work

from app.db.source_repository import (
    _COUNTER_FIELDS,
    _MERGE_CHUNK,
    _MERGE_SOURCE,
    PromotionError,
    _execute,
    _runner,
)
from app.knowledge_provisional.plan import ProvisionalPlan

CLAIM_LABEL = "ProvisionalClaim"
EVIDENCE_LABEL = "ProvisionalEvidence"
CREATED_BY = "provisional_research_ingest"

PROVISIONAL_SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT provisionalclaim_id_unique IF NOT EXISTS "
    "FOR (c:ProvisionalClaim) REQUIRE c.claim_id IS UNIQUE",
    "CREATE CONSTRAINT provisionalevidence_id_unique IF NOT EXISTS "
    "FOR (e:ProvisionalEvidence) REQUIRE e.evidence_id IS UNIQUE",
    "CREATE INDEX provisionalclaim_dataset IF NOT EXISTS "
    "FOR (c:ProvisionalClaim) ON (c.dataset_id)",
)

_MERGE_CONCEPT = """
MERGE (n:{label} {{{id_property}: $concept_id}})
ON CREATE SET n += $properties,
              n.created_by = $created_by,
              n.concept_status = 'provisional',
              n.dataset_id = $dataset_id,
              n.provisional_batch_id = $batch_id,
              n.created_at = $now
"""
_MERGE_EVIDENCE = f"""
MATCH (c:SourceChunk {{chunk_id: $chunk_id}})
MERGE (e:{EVIDENCE_LABEL} {{evidence_id: $evidence_id}})
ON CREATE SET e.provisional_batch_id = $batch_id, e.created_at = $now
SET e += $properties
MERGE (e)-[r:FROM_CHUNK]->(c)
SET r.passage_index = $passage_index, r.quote_start = $start, r.quote_end = $end
"""
_MERGE_CLAIM = """
MATCH (subject:{subject_label} {{{subject_id_property}: $subject_id}})
MATCH (object:{object_label} {{{object_id_property}: $object_id}})
MERGE (claim:ProvisionalClaim {{claim_id: $claim_id}})
ON CREATE SET claim.provisional_batch_id = $batch_id, claim.created_at = $now
SET claim += $properties
MERGE (subject)-[:PROVISIONAL_SUBJECT_OF]->(claim)
MERGE (claim)-[:PROVISIONAL_OBJECT_OF]->(object)
RETURN claim.claim_id AS claim_id
"""
_LINK_SUPPORT = f"""
MATCH (e:{EVIDENCE_LABEL} {{evidence_id: $evidence_id}})
MATCH (claim:{CLAIM_LABEL} {{claim_id: $claim_id}})
MERGE (e)-[:PROVISIONALLY_SUPPORTS]->(claim)
"""
_LINK_QUALIFIES = f"""
MATCH (e:{EVIDENCE_LABEL} {{evidence_id: $evidence_id}})
MATCH (claim:{CLAIM_LABEL} {{claim_id: $claim_id}})
MERGE (e)-[:PROVISIONALLY_QUALIFIES]->(claim)
"""


def _write_evidence(run, plan: ProvisionalPlan, evidence_id: str, common: dict) -> None:
    ev = plan.evidence[evidence_id]
    source = plan.sources[ev.source_id]
    if not run(_MERGE_SOURCE, source_id=ev.source_id, content_sha256=source["content_sha256"],
               properties=source["properties"], **common):
        raise PromotionError(
            f"Source {ev.source_id} exists in the graph with different file content; "
            "nothing was written for this item."
        )
    chunk = plan.chunks[ev.chunk_id]
    run(_MERGE_CHUNK, source_id=ev.source_id, chunk_id=ev.chunk_id,
        properties=chunk["properties"], **common)
    run(_MERGE_EVIDENCE, chunk_id=ev.chunk_id, evidence_id=evidence_id,
        properties=ev.properties, passage_index=ev.passage_index,
        start=ev.span[0], end=ev.span[1], **common)


def write_claim(tx, claim_id: str, plan: ProvisionalPlan, batch_id: str, now: str) -> dict[str, int]:
    counters = dict.fromkeys(_COUNTER_FIELDS, 0)
    run = _runner(tx, counters)
    common = {"batch_id": batch_id, "now": now}
    claim = plan.claims[claim_id]
    subject_id, _, object_id = claim.triple
    for concept_id in (subject_id, object_id):
        concept = plan.concepts[concept_id]
        run(_MERGE_CONCEPT.format(label=concept["label"], id_property=concept["id_property"]),
            concept_id=concept_id, properties=concept["properties"], created_by=CREATED_BY,
            dataset_id=plan.dataset_id, **common)
    for evidence_id in claim.evidence_ids + claim.qualifier_ids:
        _write_evidence(run, plan, evidence_id, common)
    subject, obj = plan.concepts[subject_id], plan.concepts[object_id]
    records = run(
        _MERGE_CLAIM.format(subject_label=subject["label"], subject_id_property=subject["id_property"],
                            object_label=obj["label"], object_id_property=obj["id_property"]),
        subject_id=subject_id, object_id=object_id, claim_id=claim_id,
        properties=claim.properties, **common,
    )
    if len(records) != 1:
        raise PromotionError(f"Provisional claim {claim_id} could not be linked to its concepts.")
    for evidence_id in claim.evidence_ids:
        run(_LINK_SUPPORT, evidence_id=evidence_id, claim_id=claim_id)
    for evidence_id in claim.qualifier_ids:
        run(_LINK_QUALIFIES, evidence_id=evidence_id, claim_id=claim_id)
    return counters


def write_reference(tx, evidence_id: str, plan: ProvisionalPlan, batch_id: str, now: str) -> dict[str, int]:
    counters = dict.fromkeys(_COUNTER_FIELDS, 0)
    _write_evidence(_runner(tx, counters), plan, evidence_id, {"batch_id": batch_id, "now": now})
    return counters


@dataclass
class WriteReport:
    batch_id: str
    applied: bool = False
    claims_written: int = 0
    references_written: int = 0
    counters: dict[str, int] = field(default_factory=dict)
    schema_statements: list[str] = field(default_factory=list)


def apply_schema(driver: Driver) -> list[str]:
    from app.db.schema import SOURCE_SCHEMA_STATEMENTS

    statements = list(SOURCE_SCHEMA_STATEMENTS) + list(PROVISIONAL_SCHEMA_STATEMENTS)
    with driver.session() as session:
        for statement in statements:
            session.run(statement).consume()
    return statements


def write_plan(plan: ProvisionalPlan, driver: Driver, batch_id: str | None = None,
               with_schema: bool = True) -> WriteReport:
    batch_id = batch_id or "prov-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = WriteReport(batch_id=batch_id)
    if with_schema:
        report.schema_statements = apply_schema(driver)
    now = datetime.now(timezone.utc).isoformat()
    totals = dict.fromkeys(_COUNTER_FIELDS, 0)
    references = [e for e, ev in plan.evidence.items() if ev.role == "modern_reference"]
    for counters in _execute(driver, write_reference, references, plan, batch_id, now):
        for k, v in counters.items():
            totals[k] += v
    report.references_written = len(references)
    for counters in _execute(driver, write_claim, list(plan.claims), plan, batch_id, now):
        for k, v in counters.items():
            totals[k] += v
    report.claims_written = len(plan.claims)
    report.counters = totals
    report.applied = True
    return report


# --- read-only inspection and verification ------------------------------------

def _read(driver: Driver, cypher: str, **params) -> list[dict]:
    @unit_of_work(timeout=30)
    def work(tx):
        return [r.data() for r in tx.run(cypher, **params)]

    with driver.session(default_access_mode=READ_ACCESS) as session:
        return session.execute_read(work)


def snapshot(driver: Driver) -> dict[str, Any]:
    """Counts used before/after a write to prove what changed (read-only)."""
    labels = ("Claim", "Evidence", "DescriptiveEvidence", CLAIM_LABEL, EVIDENCE_LABEL,
              "Source", "SourceChunk", "Symptom", "Roga", "Dosha", "Dhatu",
              "TherapeuticPrinciple", "Herb", "Formulation", "Diet", "Lifestyle")
    present = {r["label"] for r in _read(driver, "CALL db.labels() YIELD label RETURN label")}
    counts = {
        label: (_read(driver, f"MATCH (n:`{label}`) RETURN count(n) AS c")[0]["c"] if label in present else 0)
        for label in labels
    }
    rel_types = {r["t"] for r in _read(driver, "CALL db.relationshipTypes() YIELD relationshipType AS t RETURN t")}
    rels = {
        t: _read(driver, f"MATCH ()-[x:`{t}`]->() RETURN count(x) AS c")[0]["c"]
        for t in sorted(rel_types)
    }
    return {"nodes": counts, "relationships": rels}


def existing_concepts(driver: Driver, plan: ProvisionalPlan) -> list[str]:
    found = []
    for concept_id, concept in plan.concepts.items():
        rows = _read(driver, f"MATCH (n:`{concept['label']}` {{`{concept['id_property']}`: $id}}) RETURN count(n) AS c",
                     id=concept_id)
        if rows and rows[0]["c"]:
            found.append(concept_id)
    return found


def verify_plan(plan: ProvisionalPlan, driver: Driver) -> dict[str, Any]:
    """Read back every planned record and compare it with the plan."""
    problems: list[str] = []
    claims = _read(driver, f"""
        MATCH (c:{CLAIM_LABEL} {{dataset_id: $dataset}})
        OPTIONAL MATCH (s)-[:PROVISIONAL_SUBJECT_OF]->(c)
        OPTIONAL MATCH (c)-[:PROVISIONAL_OBJECT_OF]->(o)
        OPTIONAL MATCH (e:{EVIDENCE_LABEL})-[:PROVISIONALLY_SUPPORTS]->(c)
        OPTIONAL MATCH (q:{EVIDENCE_LABEL})-[:PROVISIONALLY_QUALIFIES]->(c)
        RETURN c.claim_id AS id, c.verification_status AS status, c.knowledge_status AS ks,
               c.subject_id AS sid, c.object_id AS oid, c.predicate AS p, c.statement AS statement,
               collect(DISTINCT s) AS subjects, collect(DISTINCT o) AS objects,
               collect(DISTINCT e.evidence_id) AS evidence, collect(DISTINCT q.evidence_id) AS qualifiers
    """, dataset=plan.dataset_id)
    by_id = {row["id"]: row for row in claims}
    for claim_id, claim in plan.claims.items():
        row = by_id.get(claim_id)
        if row is None:
            problems.append(f"{claim_id} ({claim.key}): missing in graph")
            continue
        if row["status"] != "unverified" or row["ks"] != "provisional":
            problems.append(f"{claim_id}: status {row['status']}/{row['ks']}")
        if (row["sid"], row["p"], row["oid"]) != claim.triple:
            problems.append(f"{claim_id}: triple differs")
        if row["statement"] != claim.properties["statement"]:
            problems.append(f"{claim_id}: statement differs")
        if len(row["subjects"]) != 1 or len(row["objects"]) != 1:
            problems.append(f"{claim_id}: expected exactly one subject and one object link")
        if sorted(row["evidence"]) != sorted(claim.evidence_ids):
            problems.append(f"{claim_id}: supporting evidence differs")
        if sorted(row["qualifiers"]) != sorted(claim.qualifier_ids):
            problems.append(f"{claim_id}: qualifying evidence differs")
    extra = set(by_id) - set(plan.claims)
    if extra:
        problems.append(f"{len(extra)} unexpected provisional claims for this dataset")

    evidence = _read(driver, f"""
        MATCH (e:{EVIDENCE_LABEL} {{dataset_id: $dataset}})
        OPTIONAL MATCH (e)-[r:FROM_CHUNK]->(c:SourceChunk)-[:PART_OF]->(s:Source)
        RETURN e.evidence_id AS id, e.text AS text, e.source_id AS source_id,
               e.evidence_role AS role, c.chunk_id AS chunk_id, s.source_id AS chunk_source,
               s.content_sha256 AS sha, r.quote_start AS start, r.quote_end AS end
    """, dataset=plan.dataset_id)
    ev_by_id = {row["id"]: row for row in evidence}
    for evidence_id, ev in plan.evidence.items():
        row = ev_by_id.get(evidence_id)
        if row is None:
            problems.append(f"{evidence_id}: evidence missing")
            continue
        if row["text"] != ev.properties["text"]:
            problems.append(f"{evidence_id}: quoted text differs")
        if row["chunk_id"] != ev.chunk_id or row["chunk_source"] != ev.source_id:
            problems.append(f"{evidence_id}: provenance chain (chunk/source) differs")
        if row["sha"] != plan.sources[ev.source_id]["content_sha256"]:
            problems.append(f"{evidence_id}: source content hash differs")
        if (row["start"], row["end"]) != ev.span:
            problems.append(f"{evidence_id}: quote span differs")
        if row["role"] != ev.role:
            problems.append(f"{evidence_id}: role differs")

    leaked = _read(driver, """
        MATCH (n) WHERE (n:Claim OR n:Evidence) AND n.dataset_id = $dataset
        RETURN count(n) AS c
    """, dataset=plan.dataset_id)[0]["c"]
    if leaked:
        problems.append(f"{leaked} provisional records carry approved labels (:Claim/:Evidence)")
    crossed = _read(driver, f"""
        MATCH (:{EVIDENCE_LABEL})-[x:SUPPORTS|CONTRADICTS]->() RETURN count(x) AS c
    """)[0]["c"] + _read(driver, f"""
        MATCH ()-[x:SUBJECT_OF|OBJECT_OF]-(:{CLAIM_LABEL}) RETURN count(x) AS c
    """)[0]["c"]
    if crossed:
        problems.append(f"{crossed} approved-pathway relationships touch provisional records")
    return {
        "dataset_id": plan.dataset_id,
        "claims_expected": len(plan.claims),
        "claims_found": len(by_id),
        "evidence_expected": len(plan.evidence),
        "evidence_found": len(ev_by_id),
        "problems": problems,
        "status": "verified" if not problems else "mismatch",
    }
