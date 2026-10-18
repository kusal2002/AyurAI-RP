import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class GraphService:
    """Provides knowledge graph querying, multi-hop pathway discovery,

    and subgraph extraction with live Neo4j and offline JSON fallback.
    """

    def __init__(self):
        self.neo4j = Neo4jClient()
        self._load_local_data()

    def _load_local_data(self):
        try:
            with open(DATA_DIR / "herbs_anemia.json", "r", encoding="utf-8") as f:
                self.herbs = json.load(f)
            with open(DATA_DIR / "pharma_drugs.json", "r", encoding="utf-8") as f:
                self.drugs = json.load(f)
            with open(DATA_DIR / "cyp_enzymes.json", "r", encoding="utf-8") as f:
                self.cyp_enzymes = json.load(f)
            with open(DATA_DIR / "known_interactions.json", "r", encoding="utf-8") as f:
                self.interactions = json.load(f)
        except Exception as e:
            logger.error("Failed to load local graph data: %s", str(e))
            self.herbs = []
            self.drugs = []
            self.cyp_enzymes = []
            self.interactions = []

    def get_graph_stats(self) -> Dict[str, Any]:
        """Returns node and relationship statistics from Neo4j or local cache."""
        if self.neo4j.is_connected:
            try:
                node_query = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"
                rel_query = "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count"
                node_stats = {r["label"]: r["count"] for r in self.neo4j.execute_query(node_query)}
                rel_stats = {r["type"]: r["count"] for r in self.neo4j.execute_query(rel_query)}
                return {
                    "mode": "live_neo4j",
                    "status": "connected",
                    "nodes": node_stats,
                    "relationships": rel_stats,
                    "total_nodes": sum(node_stats.values()),
                    "total_relationships": sum(rel_stats.values()),
                }
            except Exception as e:
                logger.warning("Error fetching Neo4j stats: %s. Falling back to local cache.", str(e))

        # Local fallback statistics
        total_compounds = len({c for h in self.herbs for c in h.get("active_compounds", [])})
        total_targets = len({t for d in self.drugs for t in d.get("target_receptors", [])})

        return {
            "mode": "offline_fallback",
            "status": "using_local_cache",
            "nodes": {
                "Herb": len(self.herbs),
                "Drug": len(self.drugs),
                "Compound": total_compounds,
                "Enzyme": len(self.cyp_enzymes),
                "Target": total_targets,
            },
            "relationships": {
                "INTERACTS_WITH": len([i for i in self.interactions if i.get("severity", "").lower() not in ["none", "safe"]]),
                "COMPATIBLE_WITH": len([i for i in self.interactions if i.get("severity", "").lower() in ["none", "safe"]]),
            },
            "total_nodes": len(self.herbs) + len(self.drugs) + total_compounds + len(self.cyp_enzymes) + total_targets,
            "total_relationships": len(self.interactions),
        }

    def find_multi_hop_path(self, herb_name: str, drug_name: str) -> Dict[str, Any]:
        """Discovers multi-hop biochemical interaction pathways between an Ayurvedic herb and a pharmaceutical drug.

        Path: Herb -> Compound -> Enzyme/Target <- Drug
        """
        h_lower = herb_name.lower().strip()
        d_lower = drug_name.lower().strip()

        if self.neo4j.is_connected:
            cypher = """
            MATCH path = (h:Herb)-[:CONTAINS_COMPOUND]->(c:Compound)-[r:INHIBITS|INDUCES|BINDS_TO]->(mid)<-[:METABOLIZED_BY|ACTS_ON]-(d:Drug)
            WHERE toLower(h.common_name) = toLower($herb) AND toLower(d.generic_name) = toLower($drug)
            RETURN h.common_name AS herb, c.name AS compound, type(r) AS action,
                   labels(mid)[0] AS intermediary_type, coalesce(mid.name, mid.enzyme) AS intermediary,
                   d.generic_name AS drug
            LIMIT 5
            """
            records = self.neo4j.execute_query(cypher, {"herb": herb_name, "drug": drug_name})
            if records:
                return {
                    "source": "neo4j_live",
                    "herb": herb_name,
                    "drug": drug_name,
                    "paths_found": len(records),
                    "pathways": records,
                }

        # Offline local pathway reasoning fallback
        matched_herb = next((h for h in self.herbs if h["common_name"].lower() == h_lower or h_lower in h["common_name"].lower()), None)
        matched_drug = next((d for d in self.drugs if d["generic_name"].lower() == d_lower or d_lower in d["generic_name"].lower()), None)

        if not matched_herb or not matched_drug:
            return {
                "source": "local_fallback",
                "herb": herb_name,
                "drug": drug_name,
                "paths_found": 0,
                "pathways": [],
                "message": "Herb or drug entity not found in safety database."
            }

        herb_compounds = set(matched_herb.get("active_compounds", []))
        drug_enzymes = set(matched_drug.get("metabolizing_enzymes", []))
        drug_targets = set(matched_drug.get("target_receptors", []))

        pathways = []
        for cyp in self.cyp_enzymes:
            enz_name = cyp["enzyme"]
            if any(enz_name.lower() in de.lower() for de in drug_enzymes):
                # Check if any herb compound inhibits or induces this enzyme
                for comp in herb_compounds:
                    c_lower = comp.lower()
                    if any(c_lower in inh.lower() for inh in cyp.get("inhibitors", [])):
                        pathways.append({
                            "herb": matched_herb["common_name"],
                            "compound": comp,
                            "action": "INHIBITS",
                            "intermediary_type": "Enzyme",
                            "intermediary": enz_name,
                            "drug": matched_drug["generic_name"],
                            "mechanism_type": "Pharmacokinetic Clearance Impairment"
                        })
                    if any(c_lower in ind.lower() for ind in cyp.get("inducers", [])):
                        pathways.append({
                            "herb": matched_herb["common_name"],
                            "compound": comp,
                            "action": "INDUCES",
                            "intermediary_type": "Enzyme",
                            "intermediary": enz_name,
                            "drug": matched_drug["generic_name"],
                            "mechanism_type": "Pharmacokinetic Accelerated Clearance"
                        })

        # Also search for known direct interactions
        direct_interaction = next(
            (i for i in self.interactions if matched_herb["common_name"].lower() in i["herb"].lower() and matched_drug["generic_name"].lower() in i["drug"].lower()),
            None
        )

        return {
            "source": "local_fallback",
            "herb": matched_herb["common_name"],
            "drug": matched_drug["generic_name"],
            "paths_found": len(pathways),
            "pathways": pathways,
            "direct_interaction_rule": direct_interaction,
        }
