from pathlib import Path
import sys
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.patient_context import PatientContext, MedicationItem, OrganFunction
from app.models.safety_output import InteractionFinding, EvidenceGrade
from app.ml.patient_encoder import PatientEncoder
from app.ml.models.naive_context import NaiveContextModel
from app.ml.models.context_fusion_network import ContextFusionNetwork
from app.core.context_fusion import ContextFusionLayer


def test_patient_encoder_dimension_and_values():
    patient = PatientContext(
        patient_id="PT-ENC-01",
        age=68,
        gender="Female",
        pregnancy_status=False,
        current_medications=[
            MedicationItem(name="Losartan", drug_class="ARB"),
            MedicationItem(name="Atorvastatin", drug_class="Statin"),
            MedicationItem(name="Metformin", drug_class="Biguanide"),
            MedicationItem(name="Amlodipine", drug_class="CCB"),
            MedicationItem(name="Omeprazole", drug_class="PPI"),
        ],
        organ_function=OrganFunction(egfr=42.0, ckd_stage="Stage G3b", hepatic_impairment="Moderate"),
        comorbidities=["Hypertension", "Type 2 Diabetes"],
    )

    tensor = PatientEncoder.encode_patient(patient, anemia_risk_tier="High")
    assert tensor.shape == (16,), f"Expected shape (16,), got {tensor.shape}"
    assert not torch.isnan(tensor).any(), "Found NaN in encoded patient tensor"
    assert tensor[0] == 0.68  # Normalized age
    assert tensor[1] == 1.0   # Geriatric flag >= 65
    assert tensor[9] == 1.0   # Polypharmacy flag (5 meds)
    assert tensor[14] == 1.0  # Anemia high risk tier


def test_naive_context_model_m3():
    model = NaiveContextModel(graph_dim=32, patient_dim=16, hidden_dim=32, num_classes=3)
    h_graph = torch.randn(4, 32)
    x_patient = torch.randn(4, 16)

    logits = model(h_graph, x_patient)
    assert logits.shape == (4, 3)
    assert not torch.isnan(logits).any()


def test_context_fusion_network_m4():
    model = ContextFusionNetwork(graph_dim=32, patient_dim=16, hidden_dim=32, num_classes=3)
    h_graph = torch.randn(4, 32)
    x_patient = torch.randn(4, 16)

    logits, scalar_risk = model(h_graph, x_patient)
    assert logits.shape == (4, 3)
    assert scalar_risk.shape == (4,)
    assert (scalar_risk >= 0.0).all() and (scalar_risk <= 1.0).all()

    # Test single-sample predict_safety
    out = model.predict_safety(h_graph[0], x_patient[0])
    assert out["safety_tier"] in ["Low Risk", "Caution", "High Risk"]
    assert 0.0 <= out["confidence"] <= 1.0
    assert 0.0 <= out["fused_risk_score"] <= 1.0


def test_context_fusion_layer_clinical_integration():
    fusion_layer = ContextFusionLayer()
    assert fusion_layer.m4_model is not None, "M4 model checkpoint should be loaded"

    vulnerable_patient = PatientContext(
        patient_id="PT-VULN-01",
        age=72,
        gender="Male",
        current_medications=[
            MedicationItem(name="Warfarin", drug_class="Anticoagulant"),
            MedicationItem(name="Digoxin", drug_class="Cardiac Glycoside"),
            MedicationItem(name="Furosemide", drug_class="Loop Diuretic"),
            MedicationItem(name="Losartan", drug_class="ARB"),
            MedicationItem(name="Metoprolol", drug_class="Beta-blocker"),
        ],
        organ_function=OrganFunction(egfr=28.0, ckd_stage="Stage G4", hepatic_impairment="Moderate"),
        comorbidities=["Hypertension", "Heart Failure", "Chronic Kidney Disease"],
        polypharmacy=True,
    )

    finding = InteractionFinding(
        herb_or_constituent="Active constituents in Ashwagandha",
        target_drug="Warfarin",
        interaction_type="In-Silico Predicted (GAT)",
        severity="Moderate",
        mechanism="CYP metabolic modulation",
        evidence_strength=EvidenceGrade.PROBABLE,
        prediction_confidence=0.82,
    )

    score, notes = fusion_layer.fuse_context(
        base_findings=[finding],
        contraindications=[],
        patient=vulnerable_patient,
        anemia_risk_tier="High",
    )

    assert 0.0 <= score <= 1.0
    # Should flag renal impairment and polypharmacy in modifiers
    assert any("renal" in n.lower() for n in notes)
    assert any("polypharmacy" in n.lower() for n in notes)
    assert any("geriatric" in n.lower() for n in notes)
