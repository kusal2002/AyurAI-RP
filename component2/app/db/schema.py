
from neo4j import Driver

from app.db.neo4j import get_neo4j_driver

"""Node Identifiers"""
NODE_IDENTIFIERS = {
    "Symptom": "symptom_id",
    "Roga": "roga_id",
    "Dosha": "dosha_id",
    "Dhatu": "dhatu_id",
    "TherapeuticPrinciple": "principle_id",
    "Herb": "herb_id",
    "Formulation": "formulation_id",
    "Diet": "diet_id",
    "Lifestyle": "lifestyle_id",
    "Evidence": "evidence_id",
    "Claim": "claim_id",
}


def initialize_schema() -> None:
    """Create uniqueness constraints for the Component 2 ontology."""
    driver = get_neo4j_driver()

    with driver.session() as session:
        for label, identifier in NODE_IDENTIFIERS.items():
            constraint_name = f"{label.lower()}_id_unique"

            query = (
                f"CREATE CONSTRAINT {constraint_name} "
                f"IF NOT EXISTS FOR (node:{label}) "
                f"REQUIRE node.{identifier} IS UNIQUE"
            )

            session.run(query).consume()


# Stage E additions (docs/stage_e_neo4j_design.md). Additive only: every
# statement uses IF NOT EXISTS, nothing is dropped or renamed, and the
# constraints above are untouched.
SOURCE_SCHEMA_STATEMENTS = (
    "CREATE CONSTRAINT source_id_unique IF NOT EXISTS "
    "FOR (s:Source) REQUIRE s.source_id IS UNIQUE",
    "CREATE CONSTRAINT sourcechunk_id_unique IF NOT EXISTS "
    "FOR (c:SourceChunk) REQUIRE c.chunk_id IS UNIQUE",
    "CREATE INDEX sourcechunk_source_id IF NOT EXISTS "
    "FOR (c:SourceChunk) ON (c.source_id)",
    "CREATE INDEX claim_candidate_id IF NOT EXISTS "
    "FOR (c:Claim) ON (c.candidate_id)",
    # Support for descriptive (ontology v1.1) claims. Kept off :Evidence so
    # the API evidence index never loads it.
    "CREATE CONSTRAINT descriptiveevidence_id_unique IF NOT EXISTS "
    "FOR (e:DescriptiveEvidence) REQUIRE e.evidence_id IS UNIQUE",
    # Non-destructive retraction relabels claims and evidence; these
    # indexes let a re-approval find and restore them.
    "CREATE INDEX retractedclaim_claim_id IF NOT EXISTS "
    "FOR (c:RetractedClaim) ON (c.claim_id)",
    "CREATE INDEX retractedevidence_evidence_id IF NOT EXISTS "
    "FOR (e:RetractedEvidence) ON (e.evidence_id)",
)


def initialize_source_schema(
    driver: Driver | None = None,
    dry_run: bool = True,
) -> list[str]:
    """Create the Stage E source-provenance constraints and indexes.

    With dry_run=True (the default) nothing is sent to the database; the
    statements that would run are returned. Re-running with
    dry_run=False is safe: existing constraints and indexes are kept.
    """
    statements = list(SOURCE_SCHEMA_STATEMENTS)
    if dry_run:
        return statements

    db = driver if driver is not None else get_neo4j_driver()
    with db.session() as session:
        for statement in statements:
            session.run(statement).consume()
    return statements
