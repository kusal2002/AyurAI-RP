"""Read-only integrity validation of the Component 2 knowledge graph.

Every query runs in a READ session through `execute_read`, with a
per-query timeout, so this module cannot change the database even if a
query were wrong: Neo4j rejects writes in read transactions. Results are
counts and identifiers (claim, evidence, source and chunk IDs) only; no
evidence text, credentials or host names are returned.

Each check has a severity:

- `error`: the graph breaks a contract the reasoning code relies on
  (a claim without a subject, an unknown predicate, a duplicate ID).
- `warning`: provenance is incomplete or a node is unused (an orphaned
  evidence node, a source chunk without its source).
- `info`: expected states that matter for interpretation (the Stage E
  schema is not applied yet, the graph has no approved claims).

Usage:
    python -m app.db.graph_validation [--json] [--samples 5]

Exit codes: 0 no errors, 1 errors found, 3 database unavailable.
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from neo4j import READ_ACCESS, Driver, NotificationMinimumSeverity, unit_of_work

from app.db.schema import NODE_IDENTIFIERS
from app.ontology.relationships import (
    DESCRIPTIVE_RELATIONSHIP_RULES,
    RELATIONSHIP_RULES,
)


QUERY_TIMEOUT_SECONDS = 20.0
VALIDATION_VERSION = "1"

CONCEPT_LABELS = {
    label: key for label, key in NODE_IDENTIFIERS.items()
    if label not in {"Evidence", "Claim"}
}
# Every label and relationship type written by this codebase. Anything
# else in the database was written by something we do not know about.
KNOWN_LABELS = set(NODE_IDENTIFIERS) | {
    "Source", "SourceChunk", "DescriptiveEvidence", "RetractedClaim",
    "RetractedEvidence", "PractitionerFeedback",
    # Provisional research pathway (docs/knowledge_graph_schema.md §10).
    "ProvisionalClaim", "ProvisionalEvidence",
}
KNOWN_RELATIONSHIPS = {
    "SUBJECT_OF", "OBJECT_OF", "SUPPORTS", "CONTRADICTS", "REVIEWS",
    "PART_OF", "FROM_CHUNK",
    "PROVISIONAL_SUBJECT_OF", "PROVISIONAL_OBJECT_OF",
    "PROVISIONALLY_SUPPORTS", "PROVISIONALLY_QUALIFIES",
}
KNOWN_PREDICATES = set(RELATIONSHIP_RULES) | set(DESCRIPTIVE_RELATIONSHIP_RULES)
CORE_CONSTRAINTS = {f"{label.lower()}_id_unique" for label in NODE_IDENTIFIERS}
# Stage E (docs/stage_e_neo4j_design.md); applied only after approval.
STAGE_E_CONSTRAINTS = {
    "source_id_unique", "sourcechunk_id_unique", "descriptiveevidence_id_unique",
}
ID_PROPERTIES = {
    **NODE_IDENTIFIERS,
    "Source": "source_id",
    "SourceChunk": "chunk_id",
    "DescriptiveEvidence": "evidence_id",
    "PractitionerFeedback": "feedback_id",
    "ProvisionalClaim": "claim_id",
    "ProvisionalEvidence": "evidence_id",
}


@dataclass
class Finding:
    check: str
    severity: str
    count: int
    message: str
    sample_ids: list[str] = field(default_factory=list)


@dataclass
class GraphValidationReport:
    validation_version: str = VALIDATION_VERSION
    generated_at: str = ""
    server: dict = field(default_factory=dict)
    label_counts: dict[str, int] = field(default_factory=dict)
    relationship_counts: dict[str, int] = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def status(self) -> str:
        if self.errors:
            return "invalid"
        if self.warnings:
            return "valid_with_warnings"
        return "valid"

    def to_dict(self) -> dict:
        data = asdict(self)
        data.update(status=self.status, errors=self.errors, warnings=self.warnings)
        return data


class _Reader:
    """Runs bounded read-only queries in one READ session."""

    def __init__(self, session, samples: int):
        self.session = session
        self.samples = samples

    def rows(self, cypher: str, **params) -> list[dict]:
        @unit_of_work(timeout=QUERY_TIMEOUT_SECONDS)
        def work(tx):
            return [record.data() for record in tx.run(cypher, **params)]

        return self.session.execute_read(work)

    def count_and_sample(self, match: str, id_expr: str, **params) -> tuple[int, list[str]]:
        """`match` binds the offending nodes; id_expr names their ID."""
        rows = self.rows(
            f"{match} WITH {id_expr} AS id "
            "WITH count(*) AS total, collect(id)[0..$samples] AS sample "
            "RETURN total, sample",
            samples=self.samples, **params,
        )
        if not rows:
            return 0, []
        return rows[0]["total"], [str(item) for item in rows[0]["sample"] if item is not None]


def _check(report, reader, name, severity, message, match, id_expr, **params):
    total, sample = reader.count_and_sample(match, id_expr, **params)
    if total:
        report.findings.append(Finding(name, severity, total, message, sample))


def validate_graph(driver: Driver, samples: int = 5) -> GraphValidationReport:
    """Run every check. Raises the driver's exceptions if the DB is down."""
    report = GraphValidationReport(
        generated_at=datetime.now(timezone.utc).isoformat()
    )
    # Checks name labels that may not exist yet (Stage E); the server's
    # "label does not exist" notices are expected and not printed.
    with driver.session(
        default_access_mode=READ_ACCESS,
        notifications_min_severity=NotificationMinimumSeverity.OFF,
    ) as session:
        r = _Reader(session, samples)

        components = r.rows(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions, edition"
        )
        report.server = {
            row["name"]: {"versions": row["versions"], "edition": row["edition"]}
            for row in components
        }

        labels = [row["label"] for row in r.rows("CALL db.labels() YIELD label RETURN label")]
        for label in sorted(labels):
            if label in KNOWN_LABELS:
                rows = r.rows(f"MATCH (n:`{label}`) RETURN count(n) AS c")
                report.label_counts[label] = rows[0]["c"] if rows else 0
        unknown_labels = sorted(set(labels) - KNOWN_LABELS)
        if unknown_labels:
            report.findings.append(Finding(
                "unknown_labels", "warning", len(unknown_labels),
                "Labels not written by Component 2 code.", unknown_labels[:samples],
            ))

        types = [
            row["relationshipType"]
            for row in r.rows(
                "CALL db.relationshipTypes() YIELD relationshipType "
                "RETURN relationshipType"
            )
        ]
        for rel_type in sorted(types):
            if rel_type in KNOWN_RELATIONSHIPS:
                rows = r.rows(f"MATCH ()-[x:`{rel_type}`]->() RETURN count(x) AS c")
                report.relationship_counts[rel_type] = rows[0]["c"] if rows else 0
        unknown_types = sorted(set(types) - KNOWN_RELATIONSHIPS)
        if unknown_types:
            report.findings.append(Finding(
                "unknown_relationship_types", "error", len(unknown_types),
                "Relationship types outside the documented schema.",
                unknown_types[:samples],
            ))

        names = {
            row["name"]
            for row in r.rows("SHOW CONSTRAINTS YIELD name RETURN name")
        }
        missing_core = sorted(CORE_CONSTRAINTS - names)
        missing_stage_e = sorted(STAGE_E_CONSTRAINTS - names)
        report.constraints = {
            "present": sorted(names),
            "missing_core": missing_core,
            "stage_e_applied": not missing_stage_e,
        }
        if missing_core:
            report.findings.append(Finding(
                "missing_core_constraints", "error", len(missing_core),
                "Uniqueness constraints from initialize_schema() are missing.",
                missing_core[:samples],
            ))
        if missing_stage_e:
            report.findings.append(Finding(
                "stage_e_schema_not_applied", "info", len(missing_stage_e),
                "Source provenance constraints are not applied (needs approval; "
                "see docs/stage_e_neo4j_design.md).", missing_stage_e[:samples],
            ))

        present = {label for label, count in report.label_counts.items() if count}
        _claim_checks(report, r, present)
        _evidence_checks(report, r, present)
        _source_checks(report, r, present)
        _identity_checks(report, r, present, names)
        _provisional_checks(report, r, present)

        if not report.label_counts.get("Claim"):
            report.findings.append(Finding(
                "no_approved_claims", "info", 0,
                "The graph holds no :Claim nodes, so reasoning abstains "
                "(out_of_scope or insufficient_evidence) for every request.",
            ))
    return report


def _claim_checks(report, r, present):
    if "Claim" not in present:
        return
    _check(report, r, "claim_missing_required_property", "error",
           "Claims without claim_id, predicate, subject_id, object_id or verification_status.",
           "MATCH (c:Claim) WHERE c.claim_id IS NULL OR c.predicate IS NULL "
           "OR c.subject_id IS NULL OR c.object_id IS NULL "
           "OR c.verification_status IS NULL OR trim(toString(c.claim_id)) = ''",
           "coalesce(c.claim_id, elementId(c))")
    _check(report, r, "claim_unknown_predicate", "error",
           "Claims whose predicate is not in the ontology (v1.1).",
           "MATCH (c:Claim) WHERE NOT c.predicate IN $predicates",
           "c.claim_id", predicates=sorted(KNOWN_PREDICATES))
    _check(report, r, "claim_subject_link", "error",
           "Claims without exactly one SUBJECT_OF link from a node whose ID matches subject_id.",
           "MATCH (c:Claim) "
           "OPTIONAL MATCH (s)-[:SUBJECT_OF]->(c) "
           "WITH c, collect(s) AS subjects "
           "WHERE size(subjects) <> 1 OR NOT any(k IN keys(subjects[0]) "
           "WHERE k ENDS WITH '_id' AND subjects[0][k] = c.subject_id)",
           "c.claim_id")
    _check(report, r, "claim_object_link", "error",
           "Claims without exactly one OBJECT_OF link to a node whose ID matches object_id.",
           "MATCH (c:Claim) "
           "OPTIONAL MATCH (c)-[:OBJECT_OF]->(o) "
           "WITH c, collect(o) AS objects "
           "WHERE size(objects) <> 1 OR NOT any(k IN keys(objects[0]) "
           "WHERE k ENDS WITH '_id' AND objects[0][k] = c.object_id)",
           "c.claim_id")
    _check(report, r, "claim_without_supporting_evidence", "warning",
           "Claims with no SUPPORTS evidence (they cannot pass sufficiency).",
           "MATCH (c:Claim) WHERE NOT ( (:Evidence)-[:SUPPORTS]->(c) "
           "OR (:DescriptiveEvidence)-[:SUPPORTS]->(c) )",
           "c.claim_id")
    _check(report, r, "claim_unknown_verification_status", "error",
           "Claims with a verification_status outside the documented values.",
           "MATCH (c:Claim) WHERE NOT c.verification_status IN $statuses",
           "c.claim_id",
           statuses=["unverified", "literature_supported", "practitioner_verified", "disputed"])


def _evidence_checks(report, r, present):
    if "Evidence" not in present and "DescriptiveEvidence" not in present:
        return
    _check(report, r, "orphaned_evidence", "warning",
           "Evidence that supports or contradicts no claim.",
           "MATCH (e) WHERE (e:Evidence OR e:DescriptiveEvidence) "
           "AND NOT (e)-[:SUPPORTS|CONTRADICTS]->(:Claim)",
           "e.evidence_id")
    _check(report, r, "evidence_incomplete_provenance", "warning",
           "Evidence missing title, source_name or evidence_type, or all of "
           "citation/source_url/page/section.",
           "MATCH (e) WHERE (e:Evidence OR e:DescriptiveEvidence) AND ("
           "e.title IS NULL OR e.source_name IS NULL OR e.evidence_type IS NULL "
           "OR (e.citation IS NULL AND e.source_url IS NULL AND e.page IS NULL "
           "AND e.section IS NULL))",
           "e.evidence_id")
    _check(report, r, "evidence_empty_text", "warning",
           "Evidence with empty text (cannot be checked by semantic retrieval).",
           "MATCH (e) WHERE (e:Evidence OR e:DescriptiveEvidence) "
           "AND (e.text IS NULL OR trim(e.text) = '')",
           "e.evidence_id")
    _check(report, r, "evidence_chunk_link_missing", "error",
           "Evidence that names a chunk_id but has no FROM_CHUNK link to that chunk.",
           "MATCH (e) WHERE (e:Evidence OR e:DescriptiveEvidence) "
           "AND e.chunk_id IS NOT NULL "
           "AND NOT (e)-[:FROM_CHUNK]->(:SourceChunk {chunk_id: e.chunk_id})",
           "e.evidence_id")


def _source_checks(report, r, present):
    if "SourceChunk" in present:
        _check(report, r, "chunk_without_source", "error",
               "Source chunks without a PART_OF link to the Source named by their source_id.",
               "MATCH (c:SourceChunk) WHERE NOT (c)-[:PART_OF]->(:Source {source_id: c.source_id})",
               "c.chunk_id")
        _check(report, r, "unused_source_chunk", "warning",
               "Source chunks that no evidence cites.",
               "MATCH (c:SourceChunk) WHERE NOT ()-[:FROM_CHUNK]->(c)",
               "c.chunk_id")
    if "Evidence" in present or "DescriptiveEvidence" in present:
        _check(report, r, "evidence_missing_source", "error",
               "Evidence that names a source_id with no Source node.",
               "MATCH (e) WHERE (e:Evidence OR e:DescriptiveEvidence) "
               "AND e.source_id IS NOT NULL AND NOT EXISTS { "
               "MATCH (s:Source {source_id: e.source_id}) }",
               "e.evidence_id")
    if "Source" in present:
        _check(report, r, "source_missing_identity", "error",
               "Sources without content_sha256 or title (identity/version cannot be checked).",
               "MATCH (s:Source) WHERE s.content_sha256 IS NULL OR s.title IS NULL",
               "coalesce(s.source_id, elementId(s))")


def _provisional_checks(report, r, present):
    """Provisional records must stay isolated and source-traceable."""
    if "ProvisionalClaim" in present:
        _check(report, r, "provisional_claim_not_unverified", "error",
               "Provisional claims must have verification_status 'unverified' and knowledge_status 'provisional'.",
               "MATCH (c:ProvisionalClaim) WHERE c.verification_status <> 'unverified' "
               "OR coalesce(c.knowledge_status, '') <> 'provisional'",
               "c.claim_id")
        _check(report, r, "provisional_claim_links", "error",
               "Provisional claims without exactly one PROVISIONAL_SUBJECT_OF and one PROVISIONAL_OBJECT_OF link.",
               "MATCH (c:ProvisionalClaim) "
               "WHERE COUNT { (s)-[:PROVISIONAL_SUBJECT_OF]->(c) } <> 1 "
               "OR COUNT { (c)-[:PROVISIONAL_OBJECT_OF]->(o) } <> 1",
               "c.claim_id")
        _check(report, r, "provisional_claim_without_quote", "error",
               "Provisional claims with no supporting quoted evidence.",
               "MATCH (c:ProvisionalClaim) WHERE NOT (:ProvisionalEvidence)-[:PROVISIONALLY_SUPPORTS]->(c)",
               "c.claim_id")
        _check(report, r, "provisional_claim_unknown_predicate", "error",
               "Provisional claims whose predicate is not in the ontology (v1.1).",
               "MATCH (c:ProvisionalClaim) WHERE NOT c.predicate IN $predicates",
               "c.claim_id", predicates=sorted(KNOWN_PREDICATES))
        _check(report, r, "provisional_crosses_approved_pathway", "error",
               "Approved-pathway relationships (SUBJECT_OF/OBJECT_OF/SUPPORTS/CONTRADICTS) touching provisional records.",
               "MATCH (n)-[x:SUBJECT_OF|OBJECT_OF|SUPPORTS|CONTRADICTS]-(m) "
               "WHERE n:ProvisionalClaim OR n:ProvisionalEvidence",
               "type(x)")
    if "ProvisionalEvidence" in present:
        _check(report, r, "provisional_evidence_without_chunk", "error",
               "Provisional evidence without a FROM_CHUNK link to a SourceChunk of its source.",
               "MATCH (e:ProvisionalEvidence) WHERE NOT (e)-[:FROM_CHUNK]->(:SourceChunk)-[:PART_OF]->(:Source {source_id: e.source_id})",
               "e.evidence_id")
        _check(report, r, "provisional_evidence_unused", "warning",
               "Provisional claim evidence that supports no claim (modern reference statements are exempt).",
               "MATCH (e:ProvisionalEvidence) WHERE e.evidence_role <> 'modern_reference' "
               "AND NOT (e)-[:PROVISIONALLY_SUPPORTS|PROVISIONALLY_QUALIFIES]->(:ProvisionalClaim)",
               "e.evidence_id")
        _check(report, r, "provisional_evidence_empty_quote", "error",
               "Provisional evidence with an empty quote.",
               "MATCH (e:ProvisionalEvidence) WHERE e.text IS NULL OR trim(e.text) = ''",
               "e.evidence_id")


def _identity_checks(report, r, present, constraint_names):
    for label, key in ID_PROPERTIES.items():
        if label not in present:
            continue
        _check(report, r, f"{label.lower()}_missing_id", "error",
               f"{label} nodes without {key}.",
               f"MATCH (n:`{label}`) WHERE n.`{key}` IS NULL OR trim(toString(n.`{key}`)) = ''",
               "elementId(n)")
        if f"{label.lower()}_id_unique" not in constraint_names:
            _check(report, r, f"{label.lower()}_duplicate_id", "error",
                   f"{label} IDs used by more than one node (no uniqueness constraint).",
                   f"MATCH (n:`{label}`) WHERE n.`{key}` IS NOT NULL "
                   f"WITH n.`{key}` AS key, count(*) AS c WHERE c > 1",
                   "key")
    _check(report, r, "duplicate_relationships", "warning",
           "The same relationship type repeated between the same two nodes.",
           "MATCH (a)-[x]->(b) WITH a, b, type(x) AS t, count(x) AS c WHERE c > 1",
           "t")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.db.graph_validation",
        description="Read-only integrity validation of the AyurAI C2 graph.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    parser.add_argument("--samples", type=int, default=5, help="IDs to list per finding.")
    args = parser.parse_args(argv)

    from app.db.neo4j import check_neo4j, close_neo4j_driver, get_neo4j_driver

    health = check_neo4j()
    if health["status"] != "healthy":
        print(f"Database unavailable: {health['status']} ({health['detail']})")
        return 3
    try:
        report = validate_graph(get_neo4j_driver(), samples=max(0, args.samples))
    finally:
        close_neo4j_driver()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"Graph validation v{VALIDATION_VERSION}: {report.status} "
              f"({report.errors} error(s), {report.warnings} warning(s))")
        print("Server:", ", ".join(f"{k} {v['versions']}" for k, v in report.server.items()))
        print("Labels:", report.label_counts or "none")
        print("Relationships:", report.relationship_counts or "none")
        print(f"Constraints: {len(report.constraints['present'])} present; "
              f"missing core {report.constraints['missing_core'] or 'none'}; "
              f"Stage E applied: {report.constraints['stage_e_applied']}")
        for finding in report.findings:
            sample = f" e.g. {', '.join(finding.sample_ids)}" if finding.sample_ids else ""
            print(f"[{finding.severity}] {finding.check}: {finding.count} - {finding.message}{sample}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
