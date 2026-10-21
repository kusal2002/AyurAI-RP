
from typing import Any

from neo4j import Driver

from app.db.repository import resolve_symptom_reference
from app.models.c1_input import Component2ReasoningRequest, RiskTier
from app.models.c1_screening_v1 import AnyC1Payload, screening_inputs


def prepare_c2_request(
    payload: AnyC1Payload,
    driver: Driver,
) -> dict[str, Any]:
    """Map an approved C1 screening payload into a C2 request.

    Accepts the provisional contract and `c1.screening.v1`. Only explicitly
    present, unambiguously resolved symptoms are forwarded. Unknown or
    ambiguous symptoms are reported, never guessed.
    """

    inputs = screening_inputs(payload)
    risk_value = inputs["risk_level"].strip().lower()

    try:
        risk_tier = RiskTier(risk_value)
    except ValueError:
        return {
            "status": "blocked",
            "reason": "unsupported_upstream_risk_tier",
            "request": None,
            "resolved_symptoms": [],
            "unresolved_symptoms": [],
        }

    resolved_symptoms: list[dict[str, str]] = []
    unresolved_symptoms: list[dict[str, Any]] = []
    symptom_ids: list[str] = []
    seen_ids: set[str] = set()

    for name in inputs["present_symptoms"]:
        result = resolve_symptom_reference(name, driver)
        status = result["status"]

        if status == "resolved":
            record = result["symptom"]
            symptom_id = record.get("symptom_id")

            if not isinstance(symptom_id, str) or not symptom_id.strip():
                unresolved_symptoms.append(
                    {
                        "input_name": name,
                        "status": "invalid_graph_record",
                    }
                )
                continue

            symptom_id = symptom_id.strip()

            if symptom_id not in seen_ids:
                symptom_ids.append(symptom_id)
                seen_ids.add(symptom_id)

            resolved_symptoms.append(
                {
                    "input_name": name,
                    "symptom_id": symptom_id,
                    "canonical_name": str(record.get("name") or name),
                }
            )
        else:
            unresolved_symptoms.append(
                {
                    "input_name": name,
                    "status": status,
                    "candidate_ids": [
                        str(candidate["symptom_id"])
                        for candidate in result.get("candidates", [])
                        if candidate.get("symptom_id")
                    ],
                }
            )

    # C2 requires at least one canonical symptom ID.
    # Do not invent a symptom or submit an empty request.
    if not symptom_ids:
        return {
            "status": "insufficient_input",
            "reason": "no_present_symptoms_resolved",
            "request": None,
            "resolved_symptoms": resolved_symptoms,
            "unresolved_symptoms": unresolved_symptoms,
        }

    request = Component2ReasoningRequest(
        risk_tier=risk_tier,
        calibrated_confidence=inputs["calibrated_confidence"],
        symptom_ids=symptom_ids,
        urgent_clinician_review=inputs["urgent_clinician_review"],
    )

    return {
        "status": "ready",
        "reason": None,
        "request": request,
        "resolved_symptoms": resolved_symptoms,
        "unresolved_symptoms": unresolved_symptoms,
    }
