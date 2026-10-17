
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
