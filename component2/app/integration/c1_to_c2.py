
from typing import Any

from neo4j import Driver

from app.db.repository import resolve_symptom_reference
from app.models.c1_input import Component2ReasoningRequest, RiskTier
from app.models.c1_screening_payload import C1ScreeningPayload


def prepare_c2_request(
    payload: C1ScreeningPayload,
    driver: Driver,
) -> dict[str, Any]:
    """Map an approved C1 screening payload into a C2 request.

    Only explicitly present, unambiguously resolved symptoms are forwarded.
    Unknown or ambiguous symptoms are reported, never guessed.
    """

    risk_value = payload.screening_result.risk_level.strip().lower()

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

    for symptom in payload.symptoms:
        if not symptom.present:
            continue

        result = resolve_symptom_reference(symptom.name, driver)
        status = result["status"]

        if status == "resolved":
            record = result["symptom"]
            symptom_id = record.get("symptom_id")

            if not isinstance(symptom_id, str) or not symptom_id.strip():
                unresolved_symptoms.append(
                    {
                        "input_name": symptom.name,
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
                    "input_name": symptom.name,
                    "symptom_id": symptom_id,
                    "canonical_name": str(record.get("name") or symptom.name),
                }
            )
        else:
            unresolved_symptoms.append(
                {
                    "input_name": symptom.name,
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
        calibrated_confidence=(
            payload.screening_result.screening_confidence
        ),
        symptom_ids=symptom_ids,
    )

    return {
        "status": "ready",
        "reason": None,
        "request": request,
        "resolved_symptoms": resolved_symptoms,
        "unresolved_symptoms": unresolved_symptoms,
    }
