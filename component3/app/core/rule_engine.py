import json
from pathlib import Path
from typing import List, Tuple

from app.models.patient_context import PatientContext
from app.models.safety_output import (
    InteractionFinding,
    EvidenceGrade,
    EvidenceProvenance,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class RuleEngine:
    """Stage 1: Deterministic Safety Engine (M1 - Safety Floor).

    Provides strict rule checking for known herb-drug interactions,
    herb-herb interactions, and clinical contraindications without
    relying on machine learning.
    """

    def __init__(self):
        self._load_data()

    def _load_data(self):
        with open(DATA_DIR / "known_interactions.json", "r", encoding="utf-8") as f:
            self.known_interactions = json.load(f)

        with open(DATA_DIR / "herbs_anemia.json", "r", encoding="utf-8") as f:
            self.herbs_db = {h["common_name"].lower(): h for h in json.load(f)}

    def check_contraindications(self, candidate_name: str, patient: PatientContext) -> List[str]:
        """Flags strict clinical contraindications based on patient profile."""
        triggered = []
        c_lower = candidate_name.lower()

        # Pregnancy contraindications
        if patient.pregnancy_status:
            if "ashwagandha" in c_lower:
                triggered.append("Pregnancy Alert: High doses of Withania somnifera are contraindicated due to potential emmenagogue / uterine stimulant effects.")
            if "haritaki" in c_lower:
                triggered.append("Pregnancy Alert: Terminalia chebula contains purgative anthraquinones contraindicated in pregnancy.")
            if "punarnava" in c_lower and (patient.pregnancy_trimester == 1 or patient.pregnancy_trimester is None):
                triggered.append("Pregnancy Alert: Boerhavia diffusa caution in first trimester without strict obstetrician oversight.")

        # Renal impairment contraindications
        egfr = patient.organ_function.egfr
        ckd = (patient.organ_function.ckd_stage or "").lower()
        is_severe_ckd = (egfr is not None and egfr < 30) or ("g4" in ckd or "g5" in ckd or "stage 4" in ckd or "stage 5" in ckd)

        if is_severe_ckd:
            if "mandura" in c_lower or "lauha" in c_lower:
                triggered.append("Renal Alert: Mineral-bhasma / heavy iron preparations contraindicated or require nephrologist monitoring in advanced renal failure (eGFR < 30 mL/min).")
            if "yashtimadhu" in c_lower:
                triggered.append("Renal Alert: Glycyrrhiza glabra risks severe hypokalemic metabolic alkalosis and fluid retention in compromised renal function.")

        # Comorbidity specific checks
        comorbidities_lower = [c.lower() for c in patient.comorbidities]
        if any("hypertension" in c for c in comorbidities_lower):
            if "yashtimadhu" in c_lower:
                triggered.append("Cardiovascular Alert: Glycyrrhizin causes pseudoaldosteronism and blood pressure spikes; contraindicated in uncontrolled hypertension.")

        if any("peptic ulcer" in c or "gastric ulcer" in c for c in comorbidities_lower):
            if "mandura" in c_lower or "lauha" in c_lower:
                triggered.append("Gastrointestinal Alert: Iron calx (Bhasma) may exacerbate active peptic mucosa lesions or gastric erosions.")

        return triggered

    def check_known_interactions(
        self, candidate_name: str, patient: PatientContext
    ) -> List[InteractionFinding]:
        """Matches candidate herb with patient's concurrent pharmaceutical medications."""
        findings: List[InteractionFinding] = []
        c_lower = candidate_name.lower()

        med_names = [m.name.lower() for m in patient.current_medications]

        for rule in self.known_interactions:
            # Skip safe/compatible pairs: they are non-interactions
            if rule.get("severity", "").lower() in ["none", "safe"] or "safe" in rule.get("interaction_type", "").lower():
                continue

            rule_herb = rule["herb"].lower()
            rule_drug = rule["drug"].lower()

            # Check if candidate contains this herb and patient takes this drug
            if rule_herb in c_lower and any(rule_drug in m for m in med_names):
                raw_grade = rule.get("evidence_level", "Established")
                try:
                    ev_grade = EvidenceGrade(raw_grade)
                except ValueError:
                    ev_grade = EvidenceGrade.ESTABLISHED

                pmid = str(rule.get("pmid", "")).strip() if rule.get("pmid") else None
                source_id = f"PUBMED-{pmid}" if pmid else f"RULE-{rule.get('id', 'REF')}"
                source_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid and pmid.isdigit() else None
                citation = rule.get("citation") or ("AYUSH Pharmacopoeia of India Monograph" if not pmid else "PubMed Clinical Literature")
                citation_type = "PubMed Clinical Literature" if pmid else "Classical AYUSH Monograph"

                provenance = EvidenceProvenance(
                    source_id=source_id,
                    source_title=citation,
                    citation_type=citation_type,
                    pmid_or_ref=pmid,
                    grade=ev_grade,
                    source_url=source_url,
                    excerpt=rule.get("mechanism"),
                )

                finding = InteractionFinding(
                    herb_or_constituent=rule["herb"],
                    target_drug=rule["drug"],
                    interaction_type=rule.get("interaction_type", "Known Rule"),
                    severity=rule.get("severity", "Moderate"),
                    mechanism=rule.get("mechanism", "Pharmacodynamic or pharmacokinetic interaction"),
                    evidence_strength=ev_grade,
                    prediction_confidence=0.98,
                    source_refs=[provenance],
                    clinical_action=rule.get("recommended_action"),
                )
                findings.append(finding)

        return findings
