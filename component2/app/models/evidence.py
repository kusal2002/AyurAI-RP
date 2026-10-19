from enum import Enum
from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    CLASSICAL = "classical"
    MODERN_RESEARCH = "modern_research"
    CLINICAL_GUIDELINE = "clinical_guideline"
    PRACTITIONER = "practitioner"


class EvidenceRecord(BaseModel):
    evidence_id: str = Field(..., min_length=1)

    title: str = Field(..., min_length=1)

    source_name: str = Field(..., min_length=1)

    evidence_type: EvidenceType

    section: str | None = None

    page: str | None = None

    text: str = Field(..., min_length=1)

    concepts: list[str] = Field(default_factory=list)

    source_url: str | None = None

    citation: str | None = None

    practitioner_verified: bool = False