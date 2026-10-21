"""Evidence-aware traversal of AyurAI ontology knowledge chains."""

from typing import Any

from neo4j import Driver

from app.db.repository import get_connected_knowledge
from app.ontology.relationships import RELATIONSHIP_RULES
from app.reasoning.evaluator import evaluate_claim, summarize_claim_evidence


def _embedded_evidence(record: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Evidence returned with the claim by get_connected_knowledge, if any."""
    if "supporting_evidence" not in record and "contradicting_evidence" not in record:
        return None
    return [
        {"evidence": evidence, "relationship": relationship}
        for key, relationship in (
            ("supporting_evidence", "SUPPORTS"),
            ("contradicting_evidence", "CONTRADICTS"),
        )
        for evidence in record.get(key) or []
        if evidence
    ]


def trace_knowledge_chains(
    start_concept_id: str,
    driver: Driver | None = None,
    max_depth: int = 5,
    max_chains: int = 100,
    graph: Any = None,
) -> dict[str, Any]:
    """Trace existing directed ontology claims from a starting concept.

    The function follows only predicates defined in the ontology.
    It preserves claim verification status and linked evidence, prevents
    cycles within each chain, and never generates medical conclusions.
    """
    if not isinstance(start_concept_id, str) or not start_concept_id.strip():
        raise ValueError("start_concept_id must not be empty.")

    if (
        not isinstance(max_depth, int)
        or isinstance(max_depth, bool)
        or not 1 <= max_depth <= 8
    ):
        raise ValueError("max_depth must be an integer between 1 and 8.")

    if (
        not isinstance(max_chains, int)
        or isinstance(max_chains, bool)
        or max_chains < 1
    ):
        raise ValueError("max_chains must be a positive integer.")

    start_concept_id = start_concept_id.strip()
    completed_chains: list[dict[str, Any]] = []
    truncated = False
    # One graph query per distinct concept: a concept reached by several
    # chains is looked up once, and each claim's evidence comes with it.
    connected_cache: dict[str, list[dict[str, Any]]] = {}
    connected_for = graph.get_connected_knowledge if graph is not None else get_connected_knowledge
    query_count = 0

    def finish_chain(
        concept_ids: list[str],
        claims: list[dict[str, Any]],
        reason: str,
    ) -> None:
        completed_chains.append(
            {
                "concept_ids": concept_ids,
                "claims": claims,
                "terminal_concept_id": concept_ids[-1],
                "termination_reason": reason,
            }
        )

    def walk(
        current_concept_id: str,
        concept_ids: list[str],
        claims: list[dict[str, Any]],
    ) -> None:
        nonlocal truncated, query_count

        if len(completed_chains) >= max_chains:
            truncated = True
            return

        if len(claims) >= max_depth:
            finish_chain(concept_ids, claims, "max_depth")
            return

        if current_concept_id not in connected_cache:
            connected_cache[current_concept_id] = connected_for(
                current_concept_id,
                driver,
            )
            query_count += 1
        connected_records = connected_cache[current_concept_id]

        outgoing_claims = []
        seen_claim_ids: set[str] = set()
        cycle_detected = False

        for record in connected_records:
            claim = record.get("claim")

            if not isinstance(claim, dict) or claim is None:
                continue

            # Traverse only claims directed out from the current concept.
            if claim.get("subject_id") != current_concept_id:
                continue

            predicate = claim.get("predicate")
            if predicate not in RELATIONSHIP_RULES:
                continue

            claim_id = claim.get("claim_id")
            object_id = claim.get("object_id")

            if not isinstance(claim_id, str) or not claim_id.strip():
                raise ValueError(
                    "Stored ontology claim is missing a valid claim_id."
                )

            if not isinstance(object_id, str) or not object_id.strip():
                raise ValueError(
                    "Stored ontology claim is missing a valid object_id."
                )

            if claim_id in seen_claim_ids:
                continue
            seen_claim_ids.add(claim_id)

            object_id = object_id.strip()

            if object_id in concept_ids:
                cycle_detected = True
                continue

            embedded = _embedded_evidence(record)
            if embedded is not None:
                evaluation = summarize_claim_evidence(claim, embedded)
            else:
                # Records without embedded evidence (other callers or
                # minimal stand-ins): fetch it separately.
                evaluation = (
                    evaluate_claim(claim_id, driver) if graph is None
                    else evaluate_claim(claim_id, driver, graph=graph)
                )
                query_count += 1

            verification_status = (
                evaluation["verification_status"]
                if evaluation is not None
                else claim.get("verification_status", "unverified")
            )

            outgoing_claims.append(
                {
                    "claim_id": claim_id,
                    "subject_id": current_concept_id,
                    "predicate": predicate,
                    "object_id": object_id,
                    "statement": claim.get("statement"),
                    "verification_status": verification_status,
                    "evaluation": evaluation,
                    "knowledge_status": claim.get("knowledge_status", "approved"),
                    "claim_category": claim.get("claim_category"),
                    "uncertainty_notes": list(claim.get("uncertainty_notes") or []),
                    "qualifying_evidence": list(record.get("qualifying_evidence") or []),
                }
            )

        if not outgoing_claims:
            if claims:
                finish_chain(
                    concept_ids,
                    claims,
                    (
                        "cycle_prevented"
                        if cycle_detected
                        else "no_outgoing_claims"
                    ),
                )
            return

        for outgoing_claim in outgoing_claims:
            if len(completed_chains) >= max_chains:
                truncated = True
                return

            next_concept_id = outgoing_claim["object_id"]

            walk(
                next_concept_id,
                concept_ids + [next_concept_id],
                claims + [outgoing_claim],
            )

    walk(start_concept_id, [start_concept_id], [])

    unique_claims = {
        claim["claim_id"]: claim
        for chain in completed_chains
        for claim in chain["claims"]
    }

    unverified_count = sum(
        claim["verification_status"] == "unverified"
        for claim in unique_claims.values()
    )

    disputed_count = sum(
        claim["verification_status"] == "disputed"
        for claim in unique_claims.values()
    )

    conflicting_chain_count = sum(
        any(
            claim["evaluation"] is not None
            and claim["evaluation"]["evidence_summary"]["supporting_count"] > 0
            and claim["evaluation"]["evidence_summary"]["contradicting_count"] > 0
            for claim in chain["claims"]
        )
        for chain in completed_chains
    )

    return {
        "start_concept_id": start_concept_id,
        "chains": completed_chains,
        "summary": {
            "chain_count": len(completed_chains),
            "unique_claim_count": len(unique_claims),
            "unverified_claim_count": unverified_count,
            "disputed_claim_count": disputed_count,
            "chains_with_conflicting_evidence": conflicting_chain_count,
        },
        "truncated": truncated,
        "graph_queries": query_count,
        "medical_conclusion": None,
    }