"""AyurAI Component 3: Neo4j Knowledge Graph Ingestion Script.

Reads the curated datasets (30 herbs, 50 drugs, 100 interaction pairs, 10 enzymes)
and populates the Neo4j database using Cypher MERGE operations.
Also generates a standalone 'artifacts/seed_dump.cypher' file for manual execution.
"""

import json
from pathlib import Path
import re
import sys

# Ensure app package is importable
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.neo4j_client import Neo4jClient
from app.config import settings

DATA_DIR = BASE_DIR / "app" / "data"
ARTIFACTS_DIR = BASE_DIR / "artifacts"


def load_json(filename: str):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def build_cypher_statements():
    statements = []
    herbs = load_json("herbs_anemia.json")
    drugs = load_json("pharma_drugs.json")
    cyp_enzymes = load_json("cyp_enzymes.json")
    interactions = load_json("known_interactions.json")

    # 1. Constraints & Indexes
    constraints = [
        "CREATE CONSTRAINT herb_id_unique IF NOT EXISTS FOR (h:Herb) REQUIRE h.id IS UNIQUE;",
        "CREATE CONSTRAINT drug_id_unique IF NOT EXISTS FOR (d:Drug) REQUIRE d.id IS UNIQUE;",
        "CREATE CONSTRAINT compound_name_unique IF NOT EXISTS FOR (c:Compound) REQUIRE c.name IS UNIQUE;",
        "CREATE CONSTRAINT enzyme_name_unique IF NOT EXISTS FOR (e:Enzyme) REQUIRE e.name IS UNIQUE;",
        "CREATE CONSTRAINT target_name_unique IF NOT EXISTS FOR (t:Target) REQUIRE t.name IS UNIQUE;",
        "CREATE CONSTRAINT condition_name_unique IF NOT EXISTS FOR (cond:Condition) REQUIRE cond.name IS UNIQUE;",
    ]
    statements.extend(constraints)

    # 2. Ingest Herbs & Active Compounds
    for h in herbs:
        c_uses = [u.replace("'", "\\'") for u in h.get("traditional_uses", [])]
        c_name = h['common_name'].replace("'", "\\'")
        s_name = (h.get('sanskrit_name') or '').replace("'", "\\'")
        b_name = h['botanical_name'].replace("'", "\\'")
        
        statements.append(
            f"MERGE (h:Herb {{id: '{h['id']}'}}) "
            f"SET h.common_name = '{c_name}', h.sanskrit_name = '{s_name}', "
            f"h.botanical_name = '{b_name}', h.traditional_uses = {c_uses};"
        )
        for comp in h.get("active_compounds", []):
            safe_comp = comp.replace("'", "\\'")
            statements.append(
                f"MATCH (h:Herb {{id: '{h['id']}'}}) "
                f"MERGE (c:Compound {{name: '{safe_comp}'}}) "
                f"MERGE (h)-[:CONTAINS_COMPOUND]->(c);"
            )
        for cond in h.get("contraindications", []):
            safe_cond = cond.replace("'", "\\'")
            statements.append(
                f"MATCH (h:Herb {{id: '{h['id']}'}}) "
                f"MERGE (cond:Condition {{name: '{safe_cond}'}}) "
                f"MERGE (h)-[:CONTRAINDICATED_IN]->(cond);"
            )

    # 3. Ingest CYP Enzymes & Compound Interactions
    herb_comp_lookup = {c.lower(): c for h in herbs for c in h.get("active_compounds", [])}
    for cyp in cyp_enzymes:
        e_name = cyp["enzyme"].replace("'", "\\'")
        e_desc = cyp["description"].replace("'", "\\'")
        statements.append(f"MERGE (e:Enzyme {{name: '{e_name}'}}) SET e.description = '{e_desc}';")

        for inh in cyp.get("inhibitors", []):
            raw_comp = re.sub(r"\(.*?\)", "", inh).strip()
            # Match against existing herb compound if available for exact casing
            comp_name = herb_comp_lookup.get(raw_comp.lower(), raw_comp).replace("'", "\\'")
            if comp_name:
                statements.append(
                    f"MERGE (c:Compound {{name: '{comp_name}'}}) "
                    f"WITH c "
                    f"MATCH (e:Enzyme {{name: '{e_name}'}}) "
                    f"MERGE (c)-[:INHIBITS]->(e);"
                )

        for ind in cyp.get("inducers", []):
            raw_comp = re.sub(r"\(.*?\)", "", ind).strip()
            comp_name = herb_comp_lookup.get(raw_comp.lower(), raw_comp).replace("'", "\\'")
            if comp_name:
                statements.append(
                    f"MERGE (c:Compound {{name: '{comp_name}'}}) "
                    f"WITH c "
                    f"MATCH (e:Enzyme {{name: '{e_name}'}}) "
                    f"MERGE (c)-[:INDUCES]->(e);"
                )

    # 4. Ingest Pharmaceutical Drugs
    for d in drugs:
        g_name = d["generic_name"].replace("'", "\\'")
        d_class = d["drug_class"].replace("'", "\\'")
        nti = "true" if d.get("narrow_therapeutic_index", False) else "false"
        statements.append(
            f"MERGE (d:Drug {{id: '{d['id']}'}}) "
            f"SET d.generic_name = '{g_name}', d.drug_class = '{d_class}', d.narrow_therapeutic_index = {nti};"
        )
        for enz in d.get("metabolizing_enzymes", []):
            safe_enz = enz.replace("'", "\\'")
            statements.append(
                f"MATCH (d:Drug {{id: '{d['id']}'}}) "
                f"MERGE (e:Enzyme {{name: '{safe_enz}'}}) "
                f"MERGE (d)-[:METABOLIZED_BY]->(e);"
            )
        for tgt in d.get("target_receptors", []):
            safe_tgt = tgt.replace("'", "\\'")
            statements.append(
                f"MATCH (d:Drug {{id: '{d['id']}'}}) "
                f"MERGE (t:Target {{name: '{safe_tgt}'}}) "
                f"MERGE (d)-[:ACTS_ON]->(t);"
            )

    # 5. Ingest Interactions
    for inter in interactions:
        h_name = inter["herb"].replace("'", "\\'")
        d_name = inter["drug"].replace("'", "\\'")
        sev = inter.get("severity", "Moderate").replace("'", "\\'")
        mech = inter.get("mechanism", "").replace("'", "\\'")
        ev_lvl = inter.get("evidence_level", "Probable").replace("'", "\\'")
        pmid = str(inter.get("pmid", "")).replace("'", "\\'")

        if sev.lower() in ["none", "safe"]:
            statements.append(
                f"MATCH (h:Herb), (d:Drug) "
                f"WHERE toLower(h.common_name) = toLower('{h_name}') AND toLower(d.generic_name) = toLower('{d_name}') "
                f"MERGE (h)-[r:COMPATIBLE_WITH {{id: '{inter['id']}'}}]->(d) "
                f"SET r.evidence_level = '{ev_lvl}';"
            )
        else:
            statements.append(
                f"MATCH (h:Herb), (d:Drug) "
                f"WHERE toLower(h.common_name) = toLower('{h_name}') AND toLower(d.generic_name) = toLower('{d_name}') "
                f"MERGE (h)-[r:INTERACTS_WITH {{id: '{inter['id']}'}}]->(d) "
                f"SET r.severity = '{sev}', r.mechanism = '{mech}', r.evidence_level = '{ev_lvl}', r.pmid = '{pmid}';"
            )

    return statements


def main():
    statements = build_cypher_statements()
    print(f"Generated {len(statements)} Cypher statements.")

    # Save standalone Cypher dump file
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dump_file = ARTIFACTS_DIR / "seed_dump.cypher"
    with open(dump_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(statements))
    print(f"Cypher dump saved to: {dump_file}")

    # Attempt to seed live Neo4j if available
    client = Neo4jClient()
    if client.is_connected:
        print(f"Connected to Neo4j at {settings.NEO4J_URI}. Ingesting knowledge graph...")
        executed = 0
        for stmt in statements:
            try:
                clean_stmt = stmt.strip().rstrip(";")
                client.execute_write(clean_stmt)
                executed += 1
            except Exception as e:
                print(f"Warning on statement: {e}")
        print(f"Successfully executed {executed}/{len(statements)} statements to Neo4j.")
    else:
        print(f"Neo4j is currently offline. Standalone Cypher dump is ready for execution when Neo4j is started.")


if __name__ == "__main__":
    main()
