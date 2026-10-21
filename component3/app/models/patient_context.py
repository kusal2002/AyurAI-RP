from typing import List, Optional
from pydantic import BaseModel, Field


class MedicationItem(BaseModel):
    name: str = Field(..., description="Generic pharmaceutical drug name, e.g., 'Metformin', 'Omeprazole'")
    drug_class: Optional[str] = Field(None, description="Drug class, e.g., 'Proton Pump Inhibitor', 'Antidiabetic'")
    dosage: Optional[str] = Field(None, description="Dosage and frequency, e.g., '20 mg QD'")
    route: Optional[str] = Field("Oral", description="Administration route")


class OrganFunction(BaseModel):
    egfr: Optional[float] = Field(None, description="Estimated GFR in mL/min/1.73m²")
    ckd_stage: Optional[str] = Field("Normal", description="Normal, Stage G1, G2, G3a, G3b, G4, G5")
    hepatic_impairment: Optional[str] = Field("None", description="None, Mild, Moderate, Severe")
    serum_creatinine: Optional[float] = Field(None, description="mg/dL")


class PatientContext(BaseModel):
    patient_id: str = Field(..., description="De-identified patient ID, e.g., 'PT-8921'")
    age: int = Field(..., ge=0, le=120)
    gender: str = Field(..., description="'Male', 'Female', or 'Other'")
    pregnancy_status: bool = Field(False, description="True if currently pregnant")
    pregnancy_trimester: Optional[int] = Field(None, ge=1, le=3)
    lactation_status: bool = Field(False, description="True if breastfeeding")
    current_medications: List[MedicationItem] = Field(default_factory=list)
    comorbidities: List[str] = Field(default_factory=list, description="e.g. ['Hypertension', 'Type 2 Diabetes', 'CKD']")
    allergies: List[str] = Field(default_factory=list, description="Known drug/herb allergies")
    organ_function: OrganFunction = Field(default_factory=OrganFunction)
    polypharmacy: bool = Field(False, description="Auto-calculated if ≥ 5 concurrent medications")
