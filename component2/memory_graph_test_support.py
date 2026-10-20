"""In-memory synthetic knowledge graph for offline tests.

Implements the repository read functions used by reasoning over
tests/fixtures/synthetic_graph_v1.json, whose content is invented for
software testing and is not knowledge. Test-only: the service and the
CLIs always read the live graph.
"""

import json
from pathlib import Path
from typing import Any

from app.db.schema import NODE_IDENTIFIERS

SYNTHETIC_GRAPH = Path(__file__).parent / "tests" / "fixtures" / "synthetic_graph_v1.json"


def load_synthetic_graph(path: Path = SYNTHETIC_GRAPH) -> "InMemoryGraph":
    return InMemoryGraph(json.loads(Path(path).read_text(encoding="utf-8")))


class InMemoryGraph:
    """Implements the repository read functions used by reasoning."""

    def __init__(self, fixture: dict[str, Any]):
        self.fixture_name = fixture.get("fixture", "unknown")
        source = fixture["source"]
        self.concepts: dict[str, tuple[str, dict]] = {}
        for concept in fixture["concepts"]:
            props = {NODE_IDENTIFIERS[concept["label"]]: concept["id"], "name": concept["name"]}
            if concept["label"] == "Symptom":
                props["aliases"] = list(concept.get("aliases", []))
            self.concepts[concept["id"]] = (concept["label"], props)
        self.evidence: dict[str, dict] = {}
        for item in fixture["evidence"]:
            self.evidence[item["id"]] = {
                "evidence_id": item["id"],
                "title": source["title"],
                "source_name": item.get("source_name", source["source_name"]),
                "evidence_type": source["evidence_type"],
                "section": item.get("section"),
                "page": None,
                "citation": item.get("citation"),
                "source_url": None,
                "text": item["text"],
                "concepts": [],
                "practitioner_verified": False,
                "source_id": source["source_id"],
                "chunk_id": f"{source['source_id']}#chk-{item['id'].lower()}",
            }
        self.claims: dict[str, dict] = {}
        self.links: list[tuple[str, str, str]] = []
        for claim in fixture["claims"]:
            self.claims[claim["id"]] = {
                "claim_id": claim["id"], "subject_id": claim["s"], "predicate": claim["p"],
                "object_id": claim["o"], "statement": claim["statement"],
                "verification_status": claim["status"], "confidence": None,
            }
            self.links += [(e, claim["id"], "SUPPORTS") for e in claim.get("supports", [])]
            self.links += [(e, claim["id"], "CONTRADICTS") for e in claim.get("contradicts", [])]

    # repository stand-ins ------------------------------------------------
    def get_symptom(self, symptom_id, driver=None):
        entry = self.concepts.get(symptom_id)
        return dict(entry[1]) if entry and entry[0] == "Symptom" else None

    def resolve_symptom_reference(self, reference, driver=None):
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("reference must not be empty.")
        ref = reference.strip()
        folded = ref.casefold()
        found = [
            dict(props) for label, props in self.concepts.values()
            if label == "Symptom" and (
                props["symptom_id"] == ref
                or props.get("name", "").strip().casefold() == folded
                or any(alias.strip().casefold() == folded for alias in props.get("aliases", []))
            )
        ]
        if len(found) == 1:
            return {"status": "resolved", "symptom": found[0], "candidates": found}
        if found:
            return {"status": "ambiguous", "symptom": None, "candidates": found}
        return {"status": "not_found", "symptom": None, "candidates": []}

    def _evidence_for(self, claim_id, relationship):
        return [dict(self.evidence[e]) for e, c, rel in self.links
                if c == claim_id and rel == relationship and e in self.evidence]

    def get_claims_for_concept(self, concept_id, driver=None):
        out = []
        for claim in self.claims.values():
            if claim["subject_id"] == concept_id:
                out.append({"claim": dict(claim), "role": "subject"})
            if claim["object_id"] == concept_id:
                out.append({"claim": dict(claim), "role": "object"})
        return out

    def get_connected_knowledge(self, concept_id, driver=None):
        return [
            {
                "claim": item["claim"],
                "supporting_evidence": self._evidence_for(item["claim"]["claim_id"], "SUPPORTS"),
                "contradicting_evidence": self._evidence_for(item["claim"]["claim_id"], "CONTRADICTS"),
            }
            for item in self.get_claims_for_concept(concept_id)
        ]

    def get_evidence_for_claim(self, claim_id, driver=None):
        claim = self.claims.get(claim_id)
        if claim is None:
            return None
        return {"claim": dict(claim), "evidence": [
            {"evidence": dict(self.evidence[e]), "relationship": rel}
            for e, c, rel in self.links if c == claim_id and e in self.evidence
        ]}

    def get_concepts(self, concept_ids, driver=None):
        return {cid: {"labels": [self.concepts[cid][0]], "properties": dict(self.concepts[cid][1])}
                for cid in concept_ids if cid in self.concepts}

    def list_evidence(self, driver=None, limit=10000):
        return [dict(e) for _, e in sorted(self.evidence.items())][:limit]

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for label, _ in self.concepts.values():
            counts[label] = counts.get(label, 0) + 1
        counts["Claim"] = len(self.claims)
        counts["Evidence"] = len(self.evidence)
        counts["Source"] = 1
        return counts
