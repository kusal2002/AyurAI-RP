"""Structured practitioner-review feedback contract.

Feedback is an append-only review record. It never edits a Claim or its
verification status; changing verification requires a separate, explicit
and approved workflow that does not exist yet.
"""

import re
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ReviewOutcome(str, Enum):
    AGREE = "agree"
    DISAGREE = "disagree"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    UNCERTAIN = "uncertain"


class IssueCategory(str, Enum):
    NONE = "none"
    MISSING_EVIDENCE = "missing_evidence"
    CONTRADICTING_EVIDENCE = "contradicting_evidence"
    INCORRECT_RELATIONSHIP = "incorrect_relationship"
    INCORRECT_CONCEPT_MAPPING = "incorrect_concept_mapping"
    PROVENANCE_PROBLEM = "provenance_problem"
    SOURCE_MISINTERPRETED = "source_misinterpreted"
    OUT_OF_SCOPE = "out_of_scope"
    OTHER = "other"


class ReviewerRole(str, Enum):
    AYURVEDIC_PRACTITIONER = "ayurvedic_practitioner"
    RESEARCHER = "researcher"
    SUPERVISOR = "supervisor"


def _validate_ids(values: list[str], field_name: str) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not _ID_PATTERN.fullmatch(
            value.strip()
        ):
            raise ValueError(f"{field_name} contains an invalid identifier.")
        value = value.strip()
        if value not in normalized:
            normalized.append(value)
    return normalized


class PractitionerFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str = Field(
        default_factory=lambda: f"c2fb-{uuid.uuid4()}"
    )
    request_id: str
    claim_ids: list[str] = Field(default_factory=list, max_length=50)
    candidate_ids: list[str] = Field(default_factory=list, max_length=50)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    review_outcome: ReviewOutcome
    issue_category: IssueCategory
    rationale: str = Field(min_length=1, max_length=2000)
    refinement_terms: list[str] = Field(default_factory=list, max_length=10)
    suggested_concept_ids: list[str] = Field(
        default_factory=list, max_length=20
    )
    reviewer_role: ReviewerRole
    reviewer_ref: str = Field(
        description="Pseudonymous reviewer reference; not a real name."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("feedback_id", "request_id", "reviewer_ref")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        value = value.strip()
        if not _ID_PATTERN.fullmatch(value):
            raise ValueError("Identifier format is invalid.")
        return value

    @field_validator(
        "claim_ids", "candidate_ids", "evidence_ids", "suggested_concept_ids"
    )
    @classmethod
    def validate_id_lists(cls, values: list[str], info) -> list[str]:
        return _validate_ids(values, info.field_name)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rationale must not be blank.")
        return value

    @field_validator("refinement_terms")
    @classmethod
    def validate_terms(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str):
                raise ValueError("refinement_terms must be text.")
            value = " ".join(value.split())
            if not value or len(value) > 64:
                raise ValueError(
                    "Each refinement term must be 1-64 characters."
                )
            if value.casefold() not in {v.casefold() for v in normalized}:
                normalized.append(value)
        return normalized

    @model_validator(mode="after")
    def require_target(self):
        if not self.claim_ids and not self.candidate_ids:
            raise ValueError(
                "Feedback must reference at least one claim or candidate."
            )
        return self


class RefinementQuery(BaseModel):
    """Explicit, inspectable query derived from feedback.

    Built only from de-identified concept terms and stored concept names.
    """

    feedback_id: str
    query_text: str | None
    terms: list[str]
    concept_ids: list[str]
    unknown_concept_ids: list[str] = Field(default_factory=list)
