# Unit tests for Component 3 (Herb-Drug Interaction & Safety Prediction)
from app.models.c2_input import C2CandidatePackage, CandidateItem
from app.models.patient_context import PatientContext, MedicationItem, OrganFunction
from app.models.safety_output import SafetyClassification
from app.core.rule_engine import RuleEngine
from app.core.context_fusion import ContextFusionLayer
from app.core.safety_classifier import SafetyClassifier


def test_rule_engine_detects_ashwagandha_clonazepam_interaction():
    engine = RuleEngine()
    patient = PatientContext(
        patient_id="PT-TEST-01",
        age=58,
        gender="Male",
        current_medications=[
            MedicationItem(name="Clonazepam", drug_class="Benzodiazepine", dosage="0.5 mg QHS"),
            MedicationItem(name="Levothyroxine", drug_class="Thyroid Hormone", dosage="50 mcg QD"),
        ],
    )

    findings = engine.check_known_interactions("Ashwagandha", patient)
    assert len(findings) >= 1
    target_drugs = [f.target_drug for f in findings]
    assert "Clonazepam" in target_drugs or "Levothyroxine" in target_drugs


def test_rule_engine_flags_pregnancy_contraindication():
    engine = RuleEngine()
    patient = PatientContext(
        patient_id="PT-PREG-01",
        age=28,
        gender="Female",
        pregnancy_status=True,
        pregnancy_trimester=1,
    )

    alerts = engine.check_contraindications("Ashwagandha", patient)
    assert len(alerts) >= 1
    assert any("Pregnancy" in a for a in alerts)


def test_safety_classifier_evaluates_full_package():
    classifier = SafetyClassifier()

    patient = PatientContext(
        patient_id="PT-S-RAMAN-58M",
        age=58,
        gender="Male",
        current_medications=[
            MedicationItem(name="Clonazepam", drug_class="Benzodiazepine"),
            MedicationItem(name="Levothyroxine", drug_class="Thyroid"),
            MedicationItem(name="Atorvastatin", drug_class="Statin"),
        ],
        organ_function=OrganFunction(egfr=74.0, ckd_stage="Stage G2"),
        comorbidities=["Dyslipidemia", "Mild Anxiety"],
    )

    pkg = C2CandidatePackage(
        case_id="CASE-PANDU-001",
        anemia_risk_tier="Moderate",
        anemia_confidence=0.87,
        ayurvedic_interpretation="Pittaja Pandu Roga",
        symptom_summary=["Fatigue", "Pallor", "Mild Tachycardia"],
        candidates=[
            CandidateItem(
                id="REC-01",
                name="Ashwagandha",
                category="Herb",
                dose="300 mg BID",
                reasoning_score=0.82,
                rationale="Supports Ojas and Daurbalya in chronic Pandu",
            ),
            CandidateItem(
                id="REC-02",
                name="Amalaki",
                category="Herb",
                dose="500 mg QD",
                reasoning_score=0.91,
                rationale="Rich in vitamin C to facilitate iron assimilation",
            ),
        ],
    )

    report = classifier.evaluate_package(pkg, patient)
    assert report.case_id == "CASE-PANDU-001"
    assert len(report.evaluations) == 2
    # Ashwagandha has moderate interactions with Clonazepam/Levothyroxine
    ashwa_eval = next(e for e in report.evaluations if "Ashwagandha" in e.candidate_name)
    assert ashwa_eval.safety_tier in [SafetyClassification.CAUTION, SafetyClassification.HIGH_RISK]
    assert ashwa_eval.titration_plan is not None
    assert ashwa_eval.surveillance is not None
