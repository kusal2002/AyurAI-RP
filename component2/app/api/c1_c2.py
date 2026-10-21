import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.c2 import KNOWLEDGE_SCOPE_QUERY, KnowledgeScopeParam, get_research_service
from neo4j import Driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.api.c2 import _run, get_driver
from app.integration.c1_to_c2 import prepare_c2_request
from app.models.c1_screening_payload import C1ScreeningPayload
from app.models.c1_screening_v1 import C1ScreeningPayloadV1, screening_inputs
from app.models.c2_output import Component2Output
from app.models.c3_handoff import build_component3_handoff
from app.retrieval.service import (
    EvidenceRetrievalService,
    get_retrieval_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/c1",
    tags=["Component 1 to Component 2 Integration"],
)


def _upstream_flags(data) -> dict:
    inputs = screening_inputs(data)
    return {
        "input_format": inputs["format"],
        "clinician_review_required": inputs["clinician_review_required"],
        "urgent_clinician_review": inputs["urgent_clinician_review"],
    }


@router.post("/reasoning")
def reason_from_screening(
    data: C1ScreeningPayload | C1ScreeningPayloadV1,
    knowledge_scope: KnowledgeScopeParam = KNOWLEDGE_SCOPE_QUERY,
    research_service: EvidenceRetrievalService = Depends(get_research_service),
    driver: Driver = Depends(get_driver),
    retrieval_service: EvidenceRetrievalService = Depends(
        get_retrieval_service
    ),
):
    try:
        mapped = prepare_c2_request(data, driver)
    except (ServiceUnavailable, Neo4jError, OSError):
        logger.warning(
            "c1_to_c2.mapping.graph_unavailable screening_id=%s",
            data.screening_id,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "dependency": "knowledge_graph",
            },
        )

    mapping = {
        "status": mapped["status"],
        "reason": mapped["reason"],
        "resolved_symptoms": mapped["resolved_symptoms"],
        "unresolved_symptoms": mapped["unresolved_symptoms"],
    }

    if mapped["status"] != "ready":
        return {
            "status": mapped["status"],
            "screening_id": data.screening_id,
            "upstream_flags": _upstream_flags(data),
            "mapping": mapping,
            "reasoning": None,
        }

    output = _run(
        mapped["request"],
        driver,
        retrieval_service,
        knowledge_scope,
        research_service,
    )

    return {
        "status": "completed",
        "screening_id": data.screening_id,
        "upstream_flags": _upstream_flags(data),
        "mapping": mapping,
        "reasoning": output.model_dump(mode="json"),
    }


@router.post("/component3-handoff")
def component3_handoff_from_screening(
    data: C1ScreeningPayload | C1ScreeningPayloadV1,
    knowledge_scope: KnowledgeScopeParam = KNOWLEDGE_SCOPE_QUERY,
    research_service: EvidenceRetrievalService = Depends(get_research_service),
    driver: Driver = Depends(get_driver),
    retrieval_service: EvidenceRetrievalService = Depends(get_retrieval_service),
):
    """C1 screening payload in, Component 3 candidate package out."""
    result = reason_from_screening(
        data, knowledge_scope, research_service, driver, retrieval_service
    )
    if result["reasoning"] is None:
        return {**result, "handoff": None}
    output = Component2Output.model_validate(result.pop("reasoning"))
    handoff = build_component3_handoff(
        output, urgent_clinician_review=result["upstream_flags"]["urgent_clinician_review"]
    )
    return {**result, "handoff": handoff.model_dump(mode="json")}
