from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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