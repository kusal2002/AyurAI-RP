"""Offline test helpers for Component 2 (not collected as tests).

FakeGraph is an in-memory stand-in for the Neo4j repository functions so
the real symptom reasoner, chain tracer, evaluator and pipeline can run
without a database. KeywordEncoder is a deterministic TEST-ONLY encoder;
it is never used outside tests. All data here is synthetic.
"""

import re
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import numpy as np

from app.config import RetrievalSettings
from app.retrieval.service import EvidenceRetrievalService


IDENTIFIERS = {
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


class KeywordEncoder:
    """Deterministic bag-of-words encoder used only in unit tests."""

    def __init__(self, vocabulary: list[str] | None = None):
        self.vocabulary = vocabulary or [
            "pallor", "fatigue", "pandu", "indicates", "principle",
            "herb", "formulation", "diet", "lifestyle", "uses",
            "recommends", "suggests", "unrelated", "weather", "market",
        ]
        self.calls = 0

    @property
    def model_id(self) -> str:
        return "test-keyword-encoder"

    def encode(self, texts):
        self.calls += 1
        rows = []
        for text in texts:
            words = re.findall(r"[a-z]+", text.lower())
            rows.append([float(words.count(v)) for v in self.vocabulary])
        return np.array(rows, dtype=np.float32).reshape(
            len(rows), len(self.vocabulary)
        )


class FailingEncoder:
    model_id = "unavailable-test-model"

    def encode(self, texts):
        from app.retrieval.embedding import EmbeddingModelUnavailableError

        raise EmbeddingModelUnavailableError("model could not be loaded")


def full_provenance(evidence_id: str, text: str, **overrides) -> dict:
    record = {
        "evidence_id": evidence_id,
        "title": f"Synthetic test source {evidence_id}",
        "source_name": f"Synthetic fixture {evidence_id}",
        "evidence_type": "classical",
        "section": "Synthetic section",
        "page": "1",
        "text": text,
        "concepts": [],
        "source_url": None,
        "citation": f"Synthetic citation {evidence_id}",
        "practitioner_verified": False,
    }
    record.update(overrides)
    return record


class FakeGraph:
    def __init__(self):
        self.concepts: dict[str, tuple[list[str], dict]] = {}
        self.claims: dict[str, dict] = {}
        self.evidence: dict[str, dict] = {}
        self.links: list[tuple[str, str, str]] = []

    def add_concept(self, label, concept_id, name=None, extra_labels=()):
        props = {IDENTIFIERS[label]: concept_id}
        if name:
            props["name"] = name
        self.concepts[concept_id] = ([label, *extra_labels], props)

    def add_evidence(self, evidence_id, text, **overrides):
        self.evidence[evidence_id] = full_provenance(
            evidence_id, text, **overrides
        )

    def add_claim(
        self,
        claim_id,
        subject_id,
        predicate,
        object_id,
        status="literature_supported",
        statement=None,
        supports=(),
        contradicts=(),
        confidence=None,
    ):
        self.claims[claim_id] = {
            "claim_id": claim_id,
            "subject_id": subject_id,
            "predicate": predicate,
            "object_id": object_id,
            "statement": statement
            or f"Synthetic {subject_id} {predicate} {object_id}",
            "confidence": confidence,
            "verification_status": status,
        }
        self.links += [(e, claim_id, "SUPPORTS") for e in supports]
        self.links += [(e, claim_id, "CONTRADICTS") for e in contradicts]

    # Repository stand-ins -------------------------------------------------

    def get_symptom(self, symptom_id, driver=None):
        entry = self.concepts.get(symptom_id)
        if entry is None or "Symptom" not in entry[0]:
            return None
        return dict(entry[1])

    def get_claims_for_concept(self, concept_id, driver=None):
        results = []
        for claim in self.claims.values():
            if claim["subject_id"] == concept_id:
                results.append({"claim": dict(claim), "role": "subject"})
            if claim["object_id"] == concept_id:
                results.append({"claim": dict(claim), "role": "object"})
        return results

    def get_connected_knowledge(self, concept_id, driver=None):
        return [
            {"claim": dict(item["claim"])}
            for item in self.get_claims_for_concept(concept_id)
        ]

    def get_evidence_for_claim(self, claim_id, driver=None):
        claim = self.claims.get(claim_id)
        if claim is None:
            return None
        return {
            "claim": dict(claim),
            "evidence": [
                {"evidence": dict(self.evidence[e]), "relationship": rel}
                for e, c, rel in self.links
                if c == claim_id and e in self.evidence
            ],
        }

    def get_concepts(self, concept_ids, driver=None):
        return {
            cid: {
                "labels": list(self.concepts[cid][0]),
                "properties": dict(self.concepts[cid][1]),
            }
            for cid in concept_ids
            if cid in self.concepts
        }

    def list_evidence(self, driver=None):
        return [dict(e) for _, e in sorted(self.evidence.items())]

    @contextmanager
    def patched(self):
        targets = {
            "app.reasoning.symptom_reasoner.get_symptom": self.get_symptom,
            "app.reasoning.symptom_reasoner.get_claims_for_concept":
                self.get_claims_for_concept,
            "app.reasoning.knowledge_chain.get_connected_knowledge":
                self.get_connected_knowledge,
            "app.reasoning.evaluator.get_evidence_for_claim":
                self.get_evidence_for_claim,
            "app.reasoning.pipeline.get_concepts": self.get_concepts,
        }
        with ExitStack() as stack:
            for target, replacement in targets.items():
                stack.enter_context(patch(target, side_effect=replacement))
            yield self


def make_retrieval_service(graph=None, encoder=None, min_similarity=0.3):
    return EvidenceRetrievalService(
        settings=RetrievalSettings(
            embedding_model="test-keyword-encoder",
            min_similarity=min_similarity,
            top_k=5,
        ),
        encoder=encoder or KeywordEncoder(),
        evidence_loader=(
            (lambda driver: graph.list_evidence())
            if graph is not None
            else (lambda driver: [])
        ),
    )


def build_pandu_graph(
    herb_status="literature_supported",
    herb_supports=("EV-HERB",),
    herb_contradicts=(),
):
    """Synthetic Symptom -> Roga -> Principle -> four candidate types."""
    g = FakeGraph()
    g.add_concept("Symptom", "S-PALLOR", "pallor")
    g.add_concept("Roga", "R-PANDU", "pandu")
    g.add_concept("TherapeuticPrinciple", "TP-1", "synthetic principle")
    g.add_concept("Herb", "H-1", "synthetic herb")
    g.add_concept("Formulation", "F-1", "synthetic formulation")
    g.add_concept("Diet", "D-1", "synthetic diet")
    g.add_concept("Lifestyle", "L-1", "synthetic lifestyle")

    g.add_evidence("EV-IND", "Synthetic text: pallor indicates pandu.")
    g.add_evidence("EV-TP", "Synthetic text: pandu suggests principle.")
    g.add_evidence("EV-HERB", "Synthetic text: principle uses herb.")
    g.add_evidence("EV-HERB-CON", "Synthetic text: principle uses herb.")
    g.add_evidence("EV-FORM", "Synthetic text: principle uses formulation.")
    g.add_evidence("EV-DIET", "Synthetic text: principle recommends diet.")
    g.add_evidence(
        "EV-LIFE", "Synthetic text: principle recommends lifestyle."
    )

    g.add_claim(
        "CL-IND", "S-PALLOR", "INDICATES", "R-PANDU",
        statement="pallor indicates pandu", supports=["EV-IND"],
    )
    g.add_claim(
        "CL-TP", "R-PANDU", "SUGGESTS_PRINCIPLE", "TP-1",
        statement="pandu suggests principle", supports=["EV-TP"],
    )
    g.add_claim(
        "CL-HERB", "TP-1", "USES_HERB", "H-1", status=herb_status,
        statement="principle uses herb",
        supports=list(herb_supports), contradicts=list(herb_contradicts),
    )
    g.add_claim(
        "CL-FORM", "TP-1", "USES_FORMULATION", "F-1",
        statement="principle uses formulation", supports=["EV-FORM"],
    )
    g.add_claim(
        "CL-DIET", "TP-1", "RECOMMENDS_DIET", "D-1",
        statement="principle recommends diet", supports=["EV-DIET"],
    )
    g.add_claim(
        "CL-LIFE", "TP-1", "RECOMMENDS_LIFESTYLE", "L-1",
        statement="principle recommends lifestyle", supports=["EV-LIFE"],
    )
    return g
