"""Component 2 reasoning, feedback and evidence-index endpoints.

Database and retrieval dependencies are injected through FastAPI
dependencies so tests can replace them. Importing this module does not
load the embedding model.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.db.neo4j import get_neo4j_driver
from app.feedback.service import (
    DuplicateFeedbackError,
    build_refinement_query_from_store,
    feedback_audit_summary,
    save_feedback,
)
from app.governance.audit import build_audit_record, emit_audit_record
from app.models.c1_input import Component2ReasoningRequest
from app.models.c2_output import Component2Output
from app.models.c3_handoff import Component3Handoff, build_component3_handoff
from app.models.feedback import PractitionerFeedback
from app.reasoning.pipeline import run_component2_reasoning
from app.retrieval.embedding import EmbeddingModelUnavailableError
from app.retrieval.service import (
    EvidenceRetrievalService,
    get_retrieval_service,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/c2",
    tags=["Component 2 Reasoning"],
)


def get_driver() -> Driver:
    try:
        return get_neo4j_driver()
    except RuntimeError:
        # Configuration is missing; do not reveal which variable.
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "dependency": "knowledge_graph"},
        )


_GRAPH_UNAVAILABLE = HTTPException(
    status_code=503,
    detail={"status": "unavailable", "dependency": "knowledge_graph"},
)


def _run(request, driver, retrieval_service) -> Component2Output:
    try:
        output = run_component2_reasoning(
            request,
            driver=driver,
            retrieval_service=retrieval_service,
        )
    except (ServiceUnavailable, Neo4jError, OSError):
        logger.warning(
            "c2.reasoning.graph_unavailable request_id=%s",
            request.request_id,
        )
        raise _GRAPH_UNAVAILABLE
    except ValueError:
        logger.warning(
            "c2.reasoning.malformed_graph_data request_id=%s",
            request.request_id,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "reason": "malformed_knowledge_graph_data",
            },
        )

    emit_audit_record(build_audit_record(output))
    return output


@router.post("/reasoning", response_model=Component2Output)
def reason(
    request: Component2ReasoningRequest,
    driver: Driver = Depends(get_driver),
    retrieval_service: EvidenceRetrievalService = Depends(
        get_retrieval_service
    ),
) -> Component2Output:
    return _run(request, driver, retrieval_service)


@router.post("/reasoning/component3-handoff", response_model=Component3Handoff)
def reason_for_component3(
    request: Component2ReasoningRequest,
    driver: Driver = Depends(get_driver),
    retrieval_service: EvidenceRetrievalService = Depends(
        get_retrieval_service
    ),
) -> Component3Handoff:
    return build_component3_handoff(
        _run(request, driver, retrieval_service)
    )


@router.post("/feedback")
def submit_feedback(
    feedback: PractitionerFeedback,
    driver: Driver = Depends(get_driver),
    retrieval_service: EvidenceRetrievalService = Depends(
        get_retrieval_service
    ),
):
    try:
        stored = save_feedback(feedback, driver)
        refinement = build_refinement_query_from_store(feedback, driver)
    except DuplicateFeedbackError:
        raise HTTPException(
            status_code=409,
            detail={"status": "conflict", "reason": "feedback_id_exists"},
        )
    except (ServiceUnavailable, Neo4jError, OSError):
        raise _GRAPH_UNAVAILABLE

    logging.getLogger("ayurai.c2.audit").info(
        feedback_audit_summary(feedback)
    )

    retrieval = {"mode": "not_run", "results": [], "error": None}
    if refinement.query_text:
        if retrieval_service.ensure_ready(driver):
            try:
                hits = retrieval_service.search(
                    refinement.query_text, include_below_threshold=True
                )
                retrieval = {
                    "mode": "neural_embedding",
                    "model_id": retrieval_service.model_id,
                    "results": [hit.model_dump() for hit in hits],
                    "error": None,
                }
            except EmbeddingModelUnavailableError as exc:
                retrieval = {
                    "mode": "unavailable",
                    "results": [],
                    "error": str(exc),
                }
        else:
            retrieval = {
                "mode": "unavailable",
                "results": [],
                "error": retrieval_service.last_error,
            }

    return {
        "status": "recorded",
        "feedback_id": stored["feedback_id"],
        "linked_claim_ids": stored["linked_claim_ids"],
        "unknown_claim_ids": stored["unknown_claim_ids"],
        "claims_modified": False,
        "refinement_query": refinement.model_dump(),
        "refinement_retrieval": retrieval,
    }


@router.post("/evidence-index/refresh")
def refresh_evidence_index(
    driver: Driver = Depends(get_driver),
    retrieval_service: EvidenceRetrievalService = Depends(
        get_retrieval_service
    ),
):
    try:
        stats = retrieval_service.refresh(driver)
    except EmbeddingModelUnavailableError:
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "dependency": "embedding_model"},
        )
    except (ServiceUnavailable, Neo4jError, OSError):
        raise _GRAPH_UNAVAILABLE

    return {
        "status": "refreshed",
        "model_id": retrieval_service.model_id,
        **stats,
        "skipped_evidence_ids": retrieval_service.index.skipped_evidence_ids,
    }
