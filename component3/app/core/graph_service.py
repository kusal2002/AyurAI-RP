import json
import logging
from pathlib import Path
import re
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
            MATCH path = (h:Herb)-[:CONTAINS_COMPOUND]->(c:Compound)-[r:INHIBITS|INDUCES]->(mid)<-[:METABOLIZED_BY|ACTS_ON]-(d:Drug)
            WHERE toLower(h.common_name) = toLower($herb) AND toLower(d.generic_name) = toLower($drug)
            RETURN h.common_name AS herb, c.name AS compound, type(r) AS action,
                   labels(mid)[0] AS intermediary_type, mid.name AS intermediary,
                   d.generic_name AS drug
            LIMIT 5
            """
            records = self.neo4j.execute_query(cypher, {"herb": herb_name, "drug": drug_name})
            if records:
                direct_interaction = next(
                    (i for i in self.interactions if h_lower in i["herb"].lower() and d_lower in i["drug"].lower()),
                    None
                )
                return {
                    "source": "neo4j_live",
                    "herb": herb_name,
                    "drug": drug_name,
                    "paths_found": len(records),
                    "pathways": records,
                    "direct_interaction_rule": direct_interaction,
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

    def get_subgraph(
        self,
        herb: Optional[str] = None,
        drug: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Extracts a structured multi-hop safety subgraph containing herbs, compounds,

        metabolizing enzymes, pharmaceutical drugs, and clinical contraindications.
        """
        filtered_interactions = list(self.interactions)
        if herb:
            h_clean = herb.lower().strip()
            filtered_interactions = [
                i for i in filtered_interactions if h_clean in i["herb"].lower()
            ]
        if drug:
            d_clean = drug.lower().strip()
            filtered_interactions = [
                i for i in filtered_interactions if d_clean in i["drug"].lower()
            ]
        if severity:
            s_clean = severity.lower().strip()
            if s_clean not in ["", "all"]:
                filtered_interactions = [
                    i for i in filtered_interactions if i.get("severity", "").lower() == s_clean
                ]

        # Sort by severity rank if no specific pair was searched
        if not (herb and drug):
            sev_rank = {"high": 3, "moderate": 2, "low": 1, "none": 0, "safe": 0}
            filtered_interactions = sorted(
                filtered_interactions,
                key=lambda x: sev_rank.get(x.get("severity", "").lower(), 0),
                reverse=True,
            )[:limit]

        active_herb_names = {i["herb"].lower() for i in filtered_interactions}
        active_drug_names = {i["drug"].lower() for i in filtered_interactions}

        if herb:
            active_herb_names.add(herb.lower().strip())
        if drug:
            active_drug_names.add(drug.lower().strip())

        matched_herbs = [
            h for h in self.herbs
            if h["common_name"].lower() in active_herb_names
            or any(an in h["common_name"].lower() for an in active_herb_names)
        ]
        matched_drugs = [
            d for d in self.drugs
            if d["generic_name"].lower() in active_drug_names
            or any(dn in d["generic_name"].lower() for dn in active_drug_names)
        ]

        if not matched_herbs:
            matched_herbs = self.herbs[:6]
        if not matched_drugs:
            matched_drugs = self.drugs[:6]

        def slug(text: str) -> str:
            return re.sub(r"[^a-zA-Z0-9_]+", "_", text).strip("_").lower()

        nodes_map: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        # 1. Ayurvedic Herbs & Formulations
        for h in matched_herbs:
            h_id = f"herb_{slug(h['common_name'])}"
            nodes_map[h_id] = {
                "id": h_id,
                "name": h["common_name"],
                "sanskrit_name": h.get("sanskrit_name", ""),
                "botanical_name": h.get("botanical_name", ""),
                "type": "Herb",
                "category": "Ayurvedic Formulation",
                "contraindications": h.get("contraindications", []),
                "traditional_uses": h.get("traditional_uses", []),
                "active_compounds": h.get("active_compounds", []),
            }

            # Herb -> Compounds (up to 4 per herb)
            for comp in h.get("active_compounds", [])[:4]:
                c_id = f"comp_{slug(comp)}"
                if c_id not in nodes_map:
                    nodes_map[c_id] = {
                        "id": c_id,
                        "name": comp,
                        "type": "Compound",
                        "category": "Active Phytochemical",
                    }
                edges.append({
                    "id": f"edge_{h_id}_{c_id}",
                    "source": h_id,
                    "target": c_id,
                    "type": "CONTAINS_COMPOUND",
                    "label": "contains compound",
                    "severity": "Info",
                })

            # Herb -> Contraindicated Conditions
            for cond in h.get("contraindications", []):
                cond_id = f"cond_{slug(cond)}"
                if cond_id not in nodes_map:
                    nodes_map[cond_id] = {
                        "id": cond_id,
                        "name": cond,
                        "type": "Condition",
                        "category": "Clinical Contraindication",
                    }
                edges.append({
                    "id": f"edge_{h_id}_{cond_id}",
                    "source": h_id,
                    "target": cond_id,
                    "type": "CONTRAINDICATED_IN",
                    "label": "contraindicated in",
                    "severity": "High",
                })

        # 2. Pharmaceutical Drugs
        for d in matched_drugs:
            d_id = f"drug_{slug(d['generic_name'])}"
            nodes_map[d_id] = {
                "id": d_id,
                "name": d["generic_name"],
                "type": "Drug",
                "category": d.get("drug_class", "Pharmaceutical Drug"),
                "narrow_therapeutic_index": d.get("narrow_therapeutic_index", False),
                "metabolizing_enzymes": d.get("metabolizing_enzymes", []),
                "target_receptors": d.get("target_receptors", []),
            }

            # Drug -> Metabolizing Enzymes
            for enz in d.get("metabolizing_enzymes", []):
                e_id = f"enz_{slug(enz)}"
                if e_id not in nodes_map:
                    nodes_map[e_id] = {
                        "id": e_id,
                        "name": enz,
                        "type": "Enzyme",
                        "category": "Metabolizing Enzyme (CYP450)",
                    }
                edges.append({
                    "id": f"edge_{d_id}_{e_id}",
                    "source": d_id,
                    "target": e_id,
                    "type": "METABOLIZED_BY",
                    "label": "metabolized by",
                    "severity": "Info",
                })

            # Drug -> Target Receptors
            for tgt in d.get("target_receptors", []):
                t_id = f"tgt_{slug(tgt)}"
                if t_id not in nodes_map:
                    nodes_map[t_id] = {
                        "id": t_id,
                        "name": tgt,
                        "type": "Target",
                        "category": "Therapeutic Receptor Target",
                    }
                edges.append({
                    "id": f"edge_{d_id}_{t_id}",
                    "source": d_id,
                    "target": t_id,
                    "type": "ACTS_ON",
                    "label": "acts on",
                    "severity": "Info",
                })

        # 3. Compound -> Enzyme Interactions (INHIBITS / INDUCES)
        comp_lookup = {n["name"].lower(): n["id"] for n in nodes_map.values() if n["type"] == "Compound"}
        for cyp in self.cyp_enzymes:
            enz_name = cyp["enzyme"]
            e_id = f"enz_{slug(enz_name)}"
            for inh in cyp.get("inhibitors", []):
                raw = re.sub(r"\(.*?\)", "", inh).strip().lower()
                for c_name, c_id in comp_lookup.items():
                    if raw in c_name or c_name in raw:
                        if e_id not in nodes_map:
                            nodes_map[e_id] = {"id": e_id, "name": enz_name, "type": "Enzyme", "category": "CYP450 Enzyme"}
                        edges.append({
                            "id": f"edge_{c_id}_{e_id}_inh",
                            "source": c_id,
                            "target": e_id,
                            "type": "INHIBITS",
                            "label": "inhibits",
                            "severity": "Moderate",
                            "mechanism": f"{c_name.title()} inhibits hepatic clearance through {enz_name}",
                        })
            for ind in cyp.get("inducers", []):
                raw = re.sub(r"\(.*?\)", "", ind).strip().lower()
                for c_name, c_id in comp_lookup.items():
                    if raw in c_name or c_name in raw:
                        if e_id not in nodes_map:
                            nodes_map[e_id] = {"id": e_id, "name": enz_name, "type": "Enzyme", "category": "CYP450 Enzyme"}
                        edges.append({
                            "id": f"edge_{c_id}_{e_id}_ind",
                            "source": c_id,
                            "target": e_id,
                            "type": "INDUCES",
                            "label": "induces",
                            "severity": "Moderate",
                            "mechanism": f"{c_name.title()} accelerates metabolic clearance through {enz_name}",
                        })

        # 4. Direct Herb -> Drug Interactions
        for inter in filtered_interactions:
            h_name = inter["herb"]
            d_name = inter["drug"]
            h_id = f"herb_{slug(h_name)}"
            d_id = f"drug_{slug(d_name)}"

            if h_id in nodes_map and d_id in nodes_map:
                sev = inter.get("severity", "Moderate")
                rel_type = "COMPATIBLE_WITH" if sev.lower() in ["none", "safe"] else "INTERACTS_WITH"
                edges.append({
                    "id": f"edge_inter_{inter.get('id', slug(h_name + '_' + d_name))}",
                    "source": h_id,
                    "target": d_id,
                    "type": rel_type,
                    "label": f"{sev} Interaction" if rel_type == "INTERACTS_WITH" else "Compatible",
                    "severity": sev,
                    "interaction_type": inter.get("interaction_type", ""),
                    "mechanism": inter.get("mechanism", ""),
                    "evidence_level": inter.get("evidence_level", "Established"),
                    "pmid": str(inter.get("pmid", "")),
                    "citation": inter.get("citation", ""),
                    "recommended_action": inter.get("recommended_action", ""),
                })

        return {
            "mode": "live_neo4j" if self.neo4j.is_connected else "offline_fallback",
            "total_nodes": len(nodes_map),
            "total_edges": len(edges),
            "nodes": list(nodes_map.values()),
            "edges": edges,
            "stats": self.get_graph_stats(),
        }

