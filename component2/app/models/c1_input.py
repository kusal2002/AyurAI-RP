import re
import uuid
from enum import Enum
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class RiskTier(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class C1Input(BaseModel):
    case_id: str = Field(
        ...,
        min_length=1,
        description="Pseudonymous case identifier"
    )

    risk_tier: RiskTier = Field(
        ...,
        description="Anemia risk tier produced by Component 1"
    )

    calibrated_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calibrated confidence score from Component 1"
    )

    symptom_summary: list[str] = Field(
        default_factory=list,
        description="Approved symptom summary from Component 1"
    )

    derived_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Approved derived contextual information from Component 1"
    )


_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class Component2ReasoningRequest(BaseModel):
    """Approved Component 1 input accepted by the Component 2 pipeline.

    Field names follow the existing C1Input contract. The calibrated
    confidence is the Component 1 screening confidence; it is kept as
    upstream metadata only and is never reused as confidence in any
    Ayurvedic concept or candidate.

    Unknown fields are rejected so that free-text patient data cannot be
    passed through this interface by accident.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(
        default_factory=lambda: f"c2req-{uuid.uuid4()}",
        description=(
            "Correlation identifier. Must not contain patient identifiers."
        ),
    )

    risk_tier: RiskTier = Field(
        ...,
        description="Anemia risk tier produced by Component 1",
    )

    calibrated_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices(
            "calibrated_confidence",
            "screening_confidence",
        ),
        description=(
            "Component 1 screening confidence (upstream metadata only)"
        ),
    )

    symptom_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Approved canonical symptom concept identifiers",
    )

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        value = value.strip()
        if not _REQUEST_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "request_id must be 1-128 characters of letters, digits, "
                "'.', '_', ':' or '-'."
            )
        return value

    @field_validator("calibrated_confidence", mode="before")
    @classmethod
    def reject_non_numeric_confidence(cls, value: Any) -> Any:
        # bool is a subclass of int; a True/False confidence is malformed.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("calibrated_confidence must be a number.")
        return value

    @field_validator("symptom_ids", mode="before")
    @classmethod
    def normalize_symptom_ids(cls, value: Any) -> Any:
        if not isinstance(value, list):
            raise ValueError("symptom_ids must be a list.")

        normalized: list[str] = []
        seen: set[str] = set()

        for symptom_id in value:
            if not isinstance(symptom_id, str) or not symptom_id.strip():
                raise ValueError("Each symptom ID must be non-empty text.")

            symptom_id = symptom_id.strip()

            if len(symptom_id) > 128:
                raise ValueError("Symptom IDs must be at most 128 characters.")

            if symptom_id not in seen:
                normalized.append(symptom_id)
                seen.add(symptom_id)

        return normalized
