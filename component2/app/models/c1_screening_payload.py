from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    """Typed model for the provisional Component 1 API contract."""

    model_config = ConfigDict(extra="forbid")


class ScreeningResult(ContractModel):
    condition: str
    risk_level: str
    screening_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    evidence_strength: str
    status: str
    requires_clinician_review: bool


class HemoglobinResult(ContractModel):
    estimated_g_dl: float | None = Field(default=None, gt=0)
    measured_lab_g_dl: float | None = Field(default=None, gt=0)
    source: str
    clinically_validated: bool


class ModelPrediction(ContractModel):
    model: str
    class_score: float = Field(ge=0.0, le=1.0)


class ConjunctivaResult(ContractModel):
    model_predictions: list[ModelPrediction]
    quality_score: float = Field(ge=0.0, le=1.0)
    agreement: bool


class NailbedsResult(ContractModel):
    anaemia_class_score: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    estimated_hb_g_dl: float | None = Field(default=None, gt=0)
    quality_score: float | None = Field(
        default=None, ge=0.0, le=1.0
    )


class TongueResult(ContractModel):
    quality_status: str
    anaemia_prediction: str | float | bool | None = None


class PPGResult(ContractModel):
    estimated_hb_g_dl: float | None = Field(default=None, gt=0)
    signal_quality: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    status: str


class ModalityResults(ContractModel):
    conjunctiva: ConjunctivaResult
    nailbeds: NailbedsResult
    tongue: TongueResult
    ppg: PPGResult


class Symptom(ContractModel):
    name: str
    present: bool


class C1ScreeningPayload(ContractModel):
    """Provisional Component 1 -> Component 2 screening contract."""

    screening_id: str
    session_id: str
    screening_result: ScreeningResult
    hemoglobin: HemoglobinResult
    modality_results: ModalityResults
    symptoms: list[Symptom] = Field(default_factory=list)
    clinical_findings: list[dict[str, Any]] = Field(
        default_factory=list
    )
    contributing_factors: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    recommendation: str
    model_version: str
    disclaimer: str
