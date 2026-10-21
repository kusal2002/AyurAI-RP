"""Component 1 screening output, schema `c1.screening.v1`.

This is the format Component 1 now emits. Only the fields Component 2
uses are typed; modality evidence and other detail are accepted but not
read, because Component 2 does not repeat anaemia detection.

Confidence: `confidence_percent` is the calibrated screening confidence
(0-100) and is null when none is available. The `experimental_reliability_score`
is explicitly not calibrated, so it is never used as a confidence.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.c1_screening_payload import C1ScreeningPayload


class _Lenient(BaseModel):
    # Component 1 may add fields; Component 2 ignores what it does not use.
    model_config = ConfigDict(extra="ignore")


class ScreeningResultV1(_Lenient):
    risk_level: str
    confidence_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    experimental_reliability_score: float | None = None
    reliability_score_is_calibrated: bool = False
    contributing_factors: list[str] = Field(default_factory=list)
    clinician_review_required: bool = False


class QuestionnaireStatusV1(_Lenient):
    urgent_clinician_review: bool = False


class C1ScreeningPayloadV1(_Lenient):
    schema_version: Literal["c1.screening.v1"]
    screening_id: str
    session_id: str
    screening_result: ScreeningResultV1
    # Symptoms reported present; absent symptoms are simply not listed.
    symptoms: list[str] = Field(default_factory=list)
    questionnaire_status: QuestionnaireStatusV1 = Field(default_factory=QuestionnaireStatusV1)
    missing_modalities: list[str] = Field(default_factory=list)
    synthetic_fixture: bool = False
    modality_evidence: dict[str, Any] = Field(default_factory=dict)


AnyC1Payload = C1ScreeningPayload | C1ScreeningPayloadV1


def screening_inputs(payload: AnyC1Payload) -> dict[str, Any]:
    """The values Component 2 reads, from either payload format."""
    if isinstance(payload, C1ScreeningPayloadV1):
        result = payload.screening_result
        percent = result.confidence_percent
        return {
            "risk_level": result.risk_level,
            "calibrated_confidence": None if percent is None else round(percent / 100.0, 4),
            # Snake-case identifiers such as "heavy_active_bleeding" become
            # plain names; matching itself stays exact (no guessing).
            "present_symptoms": [name.replace("_", " ").strip() for name in payload.symptoms if name.strip()],
            "clinician_review_required": result.clinician_review_required,
            "urgent_clinician_review": payload.questionnaire_status.urgent_clinician_review,
            "format": payload.schema_version,
        }
    result = payload.screening_result
    return {
        "risk_level": result.risk_level,
        "calibrated_confidence": result.screening_confidence,
        "present_symptoms": [s.name for s in payload.symptoms if s.present],
        "clinician_review_required": result.requires_clinician_review,
        "urgent_clinician_review": False,
        "format": "c1-provisional",
    }
