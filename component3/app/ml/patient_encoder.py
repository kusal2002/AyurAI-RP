import numpy as np
import torch
from typing import Dict, Any, Union
from app.models.patient_context import PatientContext


class PatientEncoder:
    """Encodes patient clinical context (age, organ function, CKD stage,

    hepatic impairment, polypharmacy, and C1 anemia tier) into a
    fixed-dimensional continuous feature vector x_patient in R^16.
    """

    FEATURE_DIM = 16

    @classmethod
    def encode_patient(cls, patient: Union[PatientContext, Dict[str, Any]], anemia_risk_tier: str = "Moderate") -> torch.Tensor:
        """Converts a PatientContext object or dict into a normalized 16-D tensor."""
        vec = np.zeros(cls.FEATURE_DIM, dtype=np.float32)

        # 1. Age (normalized to [0, 1], baseline 0-100)
        age = patient.age if isinstance(patient, PatientContext) else patient.get("age", 50)
        vec[0] = min(1.0, max(0.0, float(age) / 100.0))
        vec[1] = 1.0 if age >= 65 else (0.5 if age >= 50 else 0.0)  # Geriatric indicator

        # 2. Gender
        gender = patient.gender if isinstance(patient, PatientContext) else patient.get("gender", "Female")
        vec[2] = 1.0 if str(gender).lower().startswith("f") else 0.0

        # 3. Pregnancy
        preg_status = patient.pregnancy_status if isinstance(patient, PatientContext) else patient.get("pregnancy_status", False)
        vec[3] = 1.0 if preg_status else 0.0
        preg_trim = patient.pregnancy_trimester if isinstance(patient, PatientContext) else patient.get("pregnancy_trimester")
        vec[4] = (float(preg_trim) / 3.0) if (preg_status and preg_trim) else 0.0

        # 4. Renal Function (eGFR & CKD Stage)
        organ = patient.organ_function if isinstance(patient, PatientContext) else patient.get("organ_function", {})
        egfr = organ.egfr if isinstance(organ, object) and hasattr(organ, "egfr") else organ.get("egfr", 90.0)
        if egfr is None:
            egfr = 90.0
        # eGFR normalized: lower eGFR means higher impairment
        vec[5] = min(1.0, max(0.0, float(egfr) / 120.0))

        ckd = (organ.ckd_stage if hasattr(organ, "ckd_stage") else organ.get("ckd_stage", "")) or ""
        ckd_lower = ckd.lower()
        if "g5" in ckd_lower or egfr < 15:
            vec[6] = 1.0  # Stage G5
        elif "g4" in ckd_lower or egfr < 30:
            vec[6] = 0.8  # Stage G4
        elif "g3" in ckd_lower or egfr < 60:
            vec[6] = 0.5  # Stage G3
        elif "g2" in ckd_lower or egfr < 90:
            vec[6] = 0.2  # Stage G2
        else:
            vec[6] = 0.0  # Stage G1 Normal

        # 5. Hepatic Impairment
        hep = (organ.hepatic_impairment if hasattr(organ, "hepatic_impairment") else organ.get("hepatic_impairment", "None")) or "None"
        hep_lower = hep.lower()
        if "severe" in hep_lower:
            vec[7] = 1.0
        elif "moderate" in hep_lower:
            vec[7] = 0.66
        elif "mild" in hep_lower:
            vec[7] = 0.33
        else:
            vec[7] = 0.0

        # 6. Polypharmacy & Medication Count
        meds = patient.current_medications if isinstance(patient, PatientContext) else patient.get("current_medications", [])
        num_meds = len(meds) if meds else 0
        vec[8] = min(1.0, float(num_meds) / 10.0)
        vec[9] = 1.0 if num_meds >= 5 else (0.5 if num_meds >= 3 else 0.0)

        # 7. Comorbidities Count
        comorbs = patient.comorbidities if isinstance(patient, PatientContext) else patient.get("comorbidities", [])
        num_comorbs = len(comorbs) if comorbs else 0
        vec[10] = min(1.0, float(num_comorbs) / 5.0)

        # Specific vulnerability markers
        comorbs_lower = " ".join([str(c).lower() for c in comorbs])
        vec[11] = 1.0 if "hypertension" in comorbs_lower else 0.0
        vec[12] = 1.0 if "ulcer" in comorbs_lower or "gastritis" in comorbs_lower else 0.0
        vec[13] = 1.0 if "diabetes" in comorbs_lower else 0.0

        # 8. Component 1 Anemia Severity Context
        tier_lower = anemia_risk_tier.lower()
        if "high" in tier_lower:
            vec[14] = 1.0
            vec[15] = 0.0
        elif "mod" in tier_lower:
            vec[14] = 0.5
            vec[15] = 0.5
        else:
            vec[14] = 0.0
            vec[15] = 1.0

        return torch.tensor(vec, dtype=torch.float32)
