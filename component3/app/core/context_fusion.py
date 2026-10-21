import logging
from pathlib import Path
from typing import List, Tuple, Optional
import torch

from app.models.patient_context import PatientContext
from app.models.safety_output import InteractionFinding
from app.ml.patient_encoder import PatientEncoder
from app.ml.models.context_fusion_network import ContextFusionNetwork

logger = logging.getLogger(__name__)
M4_WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "ml" / "weights" / "context_fusion_m4.pt"


class ContextFusionLayer:
    """Stage 3: Patient Context Fusion Layer (M4 - Proposed Novelty).

    Dynamically modulates raw in-silico and rule-based interaction probabilities
    by integrating patient-specific susceptibility factors:
    - Renal clearance (eGFR & CKD stage)
    - Hepatic impairment
    - Age-related pharmacokinetics
    - Polypharmacy burden (>= 5 concurrent drugs)
    - Underlying anemia severity from Component 1

    Combines deep neural vulnerability gating (M4 network) with clinical
    interpretability and deterministic contraindication safety floors.
    """

    def __init__(self):
        self.m4_model: Optional[ContextFusionNetwork] = None
        self._load_m4_model()

    def _load_m4_model(self):
        """Loads trained M4 ContextFusionNetwork if checkpoint exists."""
        if M4_WEIGHTS_PATH.exists():
            try:
                checkpoint = torch.load(M4_WEIGHTS_PATH, map_location=torch.device("cpu"), weights_only=False)
                self.m4_model = ContextFusionNetwork(
                    graph_dim=checkpoint.get("graph_dim", 32),
                    patient_dim=checkpoint.get("patient_dim", 16),
                    hidden_dim=checkpoint.get("hidden_dim", 32),
                    num_classes=checkpoint.get("num_classes", 3),
                    dropout=0.0,
                )
                self.m4_model.load_state_dict(checkpoint["model_state_dict"])
                self.m4_model.eval()
                logger.info("Successfully loaded M4 ContextFusionNetwork from %s", M4_WEIGHTS_PATH)
            except Exception as e:
                logger.warning("Could not load M4 weights: %s. Using heuristic gating.", str(e))
                self.m4_model = None

    def fuse_context(
        self,
        base_findings: List[InteractionFinding],
        contraindications: List[str],
        patient: PatientContext,
        anemia_risk_tier: str = "Moderate",
    ) -> Tuple[float, List[str]]:
        """Calculates a fused risk score and generates clinical risk modifier notes.

        Returns:
            Tuple[float, List[str]]: (fused_risk_score: 0.0 - 1.0, risk_modifiers: List[str])
        """
        modifier_notes: List[str] = []
        risk_multiplier = 1.0

        # 1. Immediate contraindications override
        if contraindications:
            risk_multiplier += 1.5 * len(contraindications)
            modifier_notes.append(f"Hard clinical contraindications triggered ({len(contraindications)} warnings).")

        # 2. Renal function modifier
        egfr = patient.organ_function.egfr
        if egfr is not None:
            if egfr < 30:
                risk_multiplier += 0.80
                modifier_notes.append(f"Severe renal impairment (eGFR {egfr} mL/min) significantly retards compound clearance.")
            elif egfr < 60:
                risk_multiplier += 0.45
                modifier_notes.append(f"Moderate renal impairment (eGFR {egfr} mL/min, Stage G3) elevates systemic drug-herb exposure.")
            elif egfr < 90:
                risk_multiplier += 0.15
                modifier_notes.append(f"Mild renal impairment (eGFR {egfr} mL/min, Stage G2) increases metabolic susceptibility.")

        # 3. Hepatic impairment modifier
        hepatic = (patient.organ_function.hepatic_impairment or "none").lower()
        if "severe" in hepatic:
            risk_multiplier += 0.90
            modifier_notes.append("Severe hepatic impairment compromises Phase I cytochrome P450 oxidation capacity.")
        elif "moderate" in hepatic:
            risk_multiplier += 0.50
            modifier_notes.append("Moderate hepatic impairment prolongs active compound elimination half-life.")
        elif "mild" in hepatic:
            risk_multiplier += 0.20
            modifier_notes.append("Mild hepatic impairment notes slight metabolic clearance delay.")

        # 4. Age-dependent pharmacodynamics
        if patient.age >= 65:
            risk_multiplier += 0.30
            modifier_notes.append(f"Geriatric physiology (Age {patient.age}) increases tissue drug sensitivity and orthostatic risk.")
        elif patient.age >= 50:
            risk_multiplier += 0.15
            modifier_notes.append(f"Mature patient (Age {patient.age}) may exhibit decreased organ reserve.")

        # 5. Polypharmacy burden
        total_meds = len(patient.current_medications)
        if total_meds >= 5 or patient.polypharmacy:
            risk_multiplier += 0.35
            modifier_notes.append(f"Polypharmacy alert ({total_meds} concurrent active pharmaceuticals) creates complex competitive binding.")
        elif total_meds >= 3:
            risk_multiplier += 0.15
            modifier_notes.append(f"Multi-drug regimen ({total_meds} concurrent medications) requires careful dosing separation.")

        # 6. Baseline Anemia Severity Context (from C1)
        if anemia_risk_tier.lower() == "high":
            risk_multiplier += 0.20
            modifier_notes.append("Patient has High Anemia Risk (C1): heightened vulnerability to cardiovascular stress or fatigue.")

        # 7. Neural M4 Gating Execution
        if self.m4_model is not None and not contraindications:
            try:
                x_patient_tensor = PatientEncoder.encode_patient(patient, anemia_risk_tier).unsqueeze(0)
                # Compute graph interaction magnitude
                max_conf = max((f.prediction_confidence for f in base_findings), default=0.10)
                # Synthetic 32-D graph representation scaled by interaction confidence
                h_graph_tensor = torch.full((1, 32), float(max_conf), dtype=torch.float32)

                m4_out = self.m4_model.predict_safety(h_graph_tensor, x_patient_tensor)
                neural_risk = m4_out["fused_risk_score"]

                # Blend neural prediction with heuristic clinical bounds
                fused_score = min(1.0, max(0.0, 0.6 * neural_risk + 0.4 * (max_conf * risk_multiplier * 0.4)))
                return round(fused_score, 3), modifier_notes
            except Exception as e:
                logger.warning("Error running M4 neural inference: %s. Falling back to heuristic fusion.", str(e))

        # Baseline heuristic calculation (or when contraindications present)
        base_risk = 0.10
        if base_findings:
            max_conf = max(f.prediction_confidence for f in base_findings)
            base_risk = max_conf * 0.50

        fused_score = min(1.0, max(0.0, base_risk * risk_multiplier))
        return round(fused_score, 3), modifier_notes
