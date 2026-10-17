from typing import List, Optional
import uuid
from datetime import datetime, timezone

from app.models.c2_input import C2CandidatePackage, CandidateItem
from app.models.patient_context import PatientContext
from app.models.safety_output import (
    SafetyAssessmentReport,
    EvaluatedCandidateSafety,
    SafetyClassification,
    InteractionFinding,
    TitrationGuidance,
    SurveillanceGuidance,
)
from app.core.rule_engine import RuleEngine
from app.core.context_fusion import ContextFusionLayer
from app.ml.inference import GraphLinkPredictor
from app.config import settings


class SafetyClassifier:
    """Stage 4: Explainable Safety Classification & Reporting.

    Assembles findings from:
    1. Rule Engine (M1)
    2. Graph ML Predictor (M2)
    3. Context Fusion Layer (M4)
    into structured, practitioner-oriented safety assessments.
    """

    def __init__(self):
        self.rule_engine = RuleEngine()
        self.link_predictor = GraphLinkPredictor()
        self.context_fusion = ContextFusionLayer()

    def evaluate_package(
        self, c2_package: C2CandidatePackage, patient: PatientContext
    ) -> SafetyAssessmentReport:
        """Evaluates all candidate recommendations from C2 against the patient context."""
        evaluated_candidates: List[EvaluatedCandidateSafety] = []
        overall_highest_severity = None
        has_high_risk = False
        has_caution = False

        for candidate in c2_package.candidates:
            eval_result = self._evaluate_single_candidate(candidate, patient, c2_package.anemia_risk_tier)
            evaluated_candidates.append(eval_result)

            if eval_result.safety_tier == SafetyClassification.HIGH_RISK:
                has_high_risk = True
                overall_highest_severity = "High Risk"
            elif eval_result.safety_tier == SafetyClassification.CAUTION and not has_high_risk:
                has_caution = True
                overall_highest_severity = "Caution"

        if has_high_risk:
            overall_tier = SafetyClassification.HIGH_RISK
        elif has_caution:
            overall_tier = SafetyClassification.CAUTION
        else:
            overall_tier = SafetyClassification.LOW_RISK
            overall_highest_severity = "Low Risk"

        assessment_id = f"SAF-{uuid.uuid4().hex[:8].upper()}"

        return SafetyAssessmentReport(
            assessment_id=assessment_id,
            case_id=c2_package.case_id,
            patient_id=patient.patient_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            overall_safety_tier=overall_tier,
            highest_severity_finding=overall_highest_severity,
            evaluations=evaluated_candidates,
            practitioner_review_required=True,
            metadata={
                "anemia_risk_tier": c2_package.anemia_risk_tier,
                "ayurvedic_interpretation": c2_package.ayurvedic_interpretation,
                "total_candidates_evaluated": len(c2_package.candidates),
            },
        )

    def _evaluate_single_candidate(
        self, candidate: CandidateItem, patient: PatientContext, anemia_tier: str
    ) -> EvaluatedCandidateSafety:
        # 1. Deterministic rules & contraindications
        contraindications = self.rule_engine.check_contraindications(candidate.name, patient)
        known_findings = self.rule_engine.check_known_interactions(candidate.name, patient)

        # 2. In-silico link prediction
        predicted_findings = self.link_predictor.predict_interactions(candidate.name, patient)

        # Combine findings without exact duplicates
        all_findings: List[InteractionFinding] = list(known_findings)
        existing_pairs = {(f.herb_or_constituent.lower(), f.target_drug.lower()) for f in known_findings}
        for pf in predicted_findings:
            if (candidate.name.lower(), pf.target_drug.lower()) not in existing_pairs:
                all_findings.append(pf)

        # 3. Context Fusion
        fused_score, modifiers = self.context_fusion.fuse_context(
            all_findings, contraindications, patient, anemia_tier
        )

        # 4. Tier Determination
        if contraindications or fused_score >= settings.HIGH_RISK_THRESHOLD:
            tier = SafetyClassification.HIGH_RISK
            summary = (
                f"High Safety Risk: Contraindications or critical drug interactions identified for {candidate.name}. "
                "Administration requires immediate physician intervention or substitution."
            )
            escalate = True
        elif all_findings or fused_score >= settings.CAUTION_THRESHOLD:
            tier = SafetyClassification.CAUTION
            summary = (
                f"Caution Advised: Moderate pharmacokinetic or pharmacodynamic interactions identified for {candidate.name}. "
                "Recommended with dose titration, timing separation, or targeted surveillance."
            )
            escalate = True if fused_score >= 0.55 else False
        else:
            tier = SafetyClassification.LOW_RISK
            summary = f"Low Safety Risk: No significant interactions or contraindications found for {candidate.name} in this clinical profile."
            escalate = False

        # 5. Tailored Titration & Surveillance Guidance
        titration, surveillance = self._generate_guidance(candidate.name, patient, all_findings, contraindications)

        return EvaluatedCandidateSafety(
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            safety_tier=tier,
            confidence=round(min(0.99, max(0.60, 1.0 - (fused_score * 0.25 if tier == SafetyClassification.LOW_RISK else 0.05))), 2),
            summary_warning=summary,
            interaction_findings=all_findings,
            contraindications_triggered=contraindications,
            patient_risk_modifiers=modifiers,
            titration_plan=titration,
            surveillance=surveillance,
            escalate_to_practitioner=escalate,
        )

    def _generate_guidance(
        self, candidate_name: str, patient: PatientContext, findings: List[InteractionFinding], contraindications: List[str]
    ) -> Tuple[Optional[TitrationGuidance], Optional[SurveillanceGuidance]]:
        c_lower = candidate_name.lower()
        titration = None
        surveillance = None

        if "ashwagandha" in c_lower:
            titration = TitrationGuidance(
                recommended_dose_adjustment="Step-down to 300 mg QD morning dose for 14d before BID escalation.",
                separation_window="Separate ≥ 5h from daytime Clonazepam or CNS depressants.",
                duration_limit="Review after 8 weeks of continuous use.",
            )
            surveillance = SurveillanceGuidance(
                lab_monitoring=["Check Serum TSH / Free T4 at 4 weeks", "Follow-up eGFR check at 8 weeks"],
                clinical_signs_to_watch=["Excessive daytime sedation", "Heart rate changes", "Agitation"],
            )
        elif "mandura" in c_lower or "lauha" in c_lower:
            titration = TitrationGuidance(
                recommended_dose_adjustment="Take with warm water or Amalaki juice after primary meal.",
                separation_window="Separate by ≥ 4 hours from Levothyroxine, antacids, and tetracyclines.",
                duration_limit="Recheck hemoglobin and iron profile after 30 days.",
            )
            surveillance = SurveillanceGuidance(
                lab_monitoring=["Serum Ferritin & Complete Blood Count at 4 weeks", "Stool for occult blood if dyspeptic"],
                clinical_signs_to_watch=["Constipation", "Epigastric pain", "Darkened stool"],
            )
        elif findings:
            titration = TitrationGuidance(
                separation_window="Administer herbal preparation at least 2 hours apart from conventional medicines.",
            )
            surveillance = SurveillanceGuidance(
                clinical_signs_to_watch=["Dizziness", "GI upset"],
            )

        return titration, surveillance
