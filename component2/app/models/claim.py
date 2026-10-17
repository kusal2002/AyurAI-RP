from enum import Enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    LITERATURE_SUPPORTED = "literature_supported"
    PRACTITIONER_VERIFIED = "practitioner_verified"
    DISPUTED = "disputed"


class Claim(BaseModel):
    claim_id: str = Field(min_length=1)

    subject_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object_id: str = Field(min_length=1)

    statement: str = Field(min_length=1)

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0
    )

    verification_status: VerificationStatus = (
        VerificationStatus.UNVERIFIED
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )