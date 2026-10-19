"""Privacy-conscious audit metadata for Component 4 integration.

An audit record contains identifiers of knowledge-base objects (claims,
evidence, candidates), retrieval/model metadata and decision outcomes.
It deliberately excludes the supplied symptom IDs, risk tier, screening
confidence and any free text, because those describe the screened person.

Note: claim IDs traversed can still indirectly reveal which symptoms were
supplied. Component 4 must decide retention and access control for these
records; this module does not implement storage, encryption or
regulatory compliance.
"""

import json
import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.c2_output import Component2Output


audit_logger = logging.getLogger("ayurai.c2.audit")


class AuditRecord(BaseModel):
    event: str = "c2.reasoning.completed"
    request_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    output_schema_version: str
    ranking_policy_ids: list[str]
    sufficiency_policy_ids: list[str]
    retrieval_mode: str
    embedding_model_id: str | None
    retrieval_error: str | None
    input_symptom_count: int
    mapped_symptom_count: int
    claim_ids_traversed: list[str]
    evidence_ids_referenced: list[str]
    evidence_ids_retrieved: list[str]
    candidate_ids_returned: list[str]
    candidate_ids_forwarded: list[str]
    sufficiency_status: str
    abstained: bool
    abstention_reasons: list[str]
    review_required: bool


def build_audit_record(output: Component2Output) -> AuditRecord:
    claim_ids: set[str] = set()
    evidence_ids: set[str] = set()

    for mapping in output.symptom_mappings:
        claim_ids |= set(mapping.indicates_claim_ids)
    for concept in output.interpretation:
        claim_ids |= set(concept.via_claim_ids)
        evidence_ids |= set(concept.supporting_evidence_ids)
        evidence_ids |= set(concept.contradicting_evidence_ids)
    for candidate in output.candidates:
        claim_ids |= set(candidate.claim_ids)
        evidence_ids |= set(candidate.supporting_evidence_ids)
        evidence_ids |= set(candidate.contradicting_evidence_ids)

    return AuditRecord(
        request_id=output.request_id,
        output_schema_version=output.schema_version,
        ranking_policy_ids=sorted(
            {c.ranking.policy_id for c in output.candidates}
        ),
        sufficiency_policy_ids=sorted(
            {c.sufficiency.policy_id for c in output.candidates}
        ),
        retrieval_mode=output.retrieval.mode,
        embedding_model_id=output.retrieval.model_id,
        retrieval_error=output.retrieval.error,
        input_symptom_count=len(output.input_symptom_ids),
        mapped_symptom_count=sum(m.found for m in output.symptom_mappings),
        claim_ids_traversed=sorted(claim_ids),
        evidence_ids_referenced=sorted(evidence_ids),
        evidence_ids_retrieved=sorted(
            {item.evidence_id for item in output.retrieved_evidence}
        ),
        candidate_ids_returned=[c.candidate_id for c in output.candidates],
        candidate_ids_forwarded=[
            c.candidate_id
            for c in output.candidates
            if c.disposition.value == "forward_for_safety_assessment"
        ],
        sufficiency_status=output.sufficiency_status.value,
        abstained=output.abstention.abstain,
        abstention_reasons=output.abstention.reasons,
        review_required=output.review_required,
    )


def emit_audit_record(record: BaseModel) -> None:
    """Write an audit record as one JSON line to the audit logger."""
    audit_logger.info(
        json.dumps(record.model_dump(mode="json"), sort_keys=True)
    )
