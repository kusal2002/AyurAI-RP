"""Evidence-aware reasoning for supplied symptom concepts."""

from typing import Any

from neo4j import Driver

from app.db.repository import get_claims_for_concept, get_symptom
from app.reasoning.evaluator import evaluate_claim


def reason_about_symptoms(
    symptom_ids: list[str],
    driver: Driver | None = None,
    graph: Any = None,
) -> dict[str, Any]:
    """Summarize evidence associated with supplied symptoms.

    This function retrieves existing Symptom -> Roga claims and evaluates
    their linked evidence. It does not diagnose, rank diseases, or prescribe.
    """
    if not isinstance(symptom_ids, list) or not symptom_ids:
        raise ValueError("symptom_ids must be a non-empty list.")

    normalized_ids: list[str] = []
    seen: set[str] = set()

    for symptom_id in symptom_ids:
        if not isinstance(symptom_id, str) or not symptom_id.strip():
            raise ValueError("Each symptom ID must be non-empty text.")

        normalized_id = symptom_id.strip()

        if normalized_id not in seen:
            normalized_ids.append(normalized_id)
            seen.add(normalized_id)

    lookup_symptom = graph.get_symptom if graph is not None else get_symptom
    claims_for = graph.get_claims_for_concept if graph is not None else get_claims_for_concept

    results = []
    found_symptom_count = 0
    indicates_claim_count = 0

    for symptom_id in normalized_ids:
        symptom = lookup_symptom(symptom_id, driver)

        if symptom is None:
            results.append(
                {
                    "symptom_id": symptom_id,
                    "found": False,
                    "symptom": None,
                    "indicates_claims": [],
                    "message": (
                        "Symptom concept was not found in the knowledge graph."
                    ),
                }
            )
            continue

        found_symptom_count += 1
        connected_claims = claims_for(symptom_id, driver)
        indicates_claims = []

        for item in connected_claims:
            claim = item.get("claim", {})

            # Only consider claims where the symptom is the subject.
            if item.get("role") != "subject":
                continue

            if claim.get("predicate") != "INDICATES":
                continue

            claim_id = claim.get("claim_id")

            if not isinstance(claim_id, str) or not claim_id.strip():
                raise ValueError(
                    "Stored INDICATES claim is missing a valid claim_id."
                )

            evaluation = (
                evaluate_claim(claim_id, driver) if graph is None
                else evaluate_claim(claim_id, driver, graph=graph)
            )

            indicates_claims.append(
                {
                    "claim_id": claim_id,
                    "roga_id": claim.get("object_id"),
                    "statement": claim.get("statement"),
                    "verification_status": (
                        evaluation["verification_status"]
                        if evaluation is not None
                        else claim.get("verification_status", "unverified")
                    ),
                    "evaluation": evaluation,
                    "knowledge_status": claim.get("knowledge_status", "approved"),
                }
            )

        indicates_claim_count += len(indicates_claims)

        results.append(
            {
                "symptom_id": symptom_id,
                "found": True,
                "symptom": symptom,
                "indicates_claims": indicates_claims,
            }
        )

    return {
        "summary": {
            "requested_symptom_count": len(symptom_ids),
            "unique_symptom_count": len(normalized_ids),
            "found_symptom_count": found_symptom_count,
            "indicates_claim_count": indicates_claim_count,
        },
        "results": results,
        "medical_conclusion": None,
    }