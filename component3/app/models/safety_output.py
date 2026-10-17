from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class SafetyClassification(str, Enum):
    LOW_RISK = "Low Risk"
    CAUTION = "Caution"
    HIGH_RISK = "High Risk"


class EvidenceGrade(str, Enum):
    ESTABLISHED = "Established"
    PROBABLE = "Probable"
    POSSIBLE = "Possible"
    INSUFFICIENT = "Insufficient"


class EvidenceProvenance(BaseModel):
    source_id: str
    source_title: str
    citation_type: str = Field(..., description="e.g. 'AYUSH Monograph', 'PubMed', 'WHO VigiBase'")
    pmid_or_ref: Optional[str] = None
    grade: EvidenceGrade = EvidenceGrade.PROBABLE


class InteractionFinding(BaseModel):
    herb_or_constituent: str
    target_drug: str
    interaction_type: str = Field(..., description="'Known Rule', 'In-Silico Predicted (GNN)', or 'Pharmacokinetic'")
    severity: str = Field(..., description="'Mild', 'Moderate', 'Severe'")
    mechanism: str = Field(..., description="e.g., 'CYP2C9 competitive inhibition', 'Chelation reducing absorption'")
    evidence_strength: EvidenceGrade = EvidenceGrade.PROBABLE
    prediction_confidence: float = Field(..., ge=0.0, le=1.0)
    source_refs: List[EvidenceProvenance] = Field(default_factory=list)


class TitrationGuidance(BaseModel):
    recommended_dose_adjustment: Optional[str] = None
    separation_window: Optional[str] = Field(None, description="e.g., 'Separate ingestion by >= 2 hours from iron/thyroxine'")
    duration_limit: Optional[str] = None


class SurveillanceGuidance(BaseModel):
    lab_monitoring: List[str] = Field(default_factory=list, description="e.g., ['Serum Ferritin at 4 weeks', 'eGFR at 8 weeks']")
    clinical_signs_to_watch: List[str] = Field(default_factory=list, description="e.g., ['Hypotension', 'Excessive drowsiness']")


class EvaluatedCandidateSafety(BaseModel):
    candidate_id: str
    candidate_name: str
    safety_tier: SafetyClassification
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary_warning: str
    interaction_findings: List[InteractionFinding] = Field(default_factory=list)
    contraindications_triggered: List[str] = Field(default_factory=list)
    patient_risk_modifiers: List[str] = Field(default_factory=list)
    titration_plan: Optional[TitrationGuidance] = None
    surveillance: Optional[SurveillanceGuidance] = None
    escalate_to_practitioner: bool = False


class SafetyAssessmentReport(BaseModel):
    assessment_id: str
    case_id: str
    patient_id: str
    timestamp: str
    overall_safety_tier: SafetyClassification
    highest_severity_finding: Optional[str] = None
    evaluations: List[EvaluatedCandidateSafety] = Field(..., description="Safety evaluation per candidate herb/formulation")
    practitioner_review_required: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
