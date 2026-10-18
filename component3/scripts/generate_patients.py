"""Synthetic Patient Profile Generator for AyurAI Component 3.

Generates 500 clinically realistic patient profiles reflecting Sri Lankan
demographics, clinical comorbidities, organ function profiles (eGFR / CKD stages),
polypharmacy regimens, and Component 1 anemia risk tiers.
Fulfills Proposal Table 2: Target Size = 500 profiles.
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Any

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

# Common Sri Lankan Clinical Comorbidities
COMMON_COMORBIDITIES = [
    "Type 2 Diabetes Mellitus",
    "Essential Hypertension",
    "Dyslipidemia",
    "Chronic Kidney Disease",
    "Ischemic Heart Disease",
    "Peptic Ulcer Disease",
    "Osteoarthritis",
    "Bronchial Asthma",
    "Hypothyroidism",
    "Gastroesophageal Reflux Disease (GERD)",
    "Non-Alcoholic Fatty Liver Disease (NAFLD)",
]

COMMON_ALLERGIES = [
    "Penicillin",
    "Sulfa drugs",
    "NSAIDs (Aspirin/Ibuprofen)",
    "Ciprofloxacin",
    "None",
    "None",
    "None",
    "None",
    "None",
]


def load_drugs_pool() -> List[Dict[str, Any]]:
    drugs_file = DATA_DIR / "pharma_drugs.json"
    if drugs_file.exists():
        with open(drugs_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def generate_single_patient(patient_idx: int, drugs_pool: List[Dict[str, Any]]) -> Dict[str, Any]:
    patient_id = f"PT-SL-{patient_idx:03d}"
    
    # Age & Gender distribution
    gender = random.choice(["Female", "Male"])
    if gender == "Female":
        # 35% chance in reproductive age (18-45) matching maternal health emphasis
        if random.random() < 0.40:
            age = random.randint(18, 45)
            pregnancy_status = random.random() < 0.25  # ~10% overall of reproductive females pregnant
            pregnancy_trimester = random.choice([1, 2, 3]) if pregnancy_status else None
        else:
            age = random.randint(46, 82)
            pregnancy_status = False
            pregnancy_trimester = None
    else:
        age = random.randint(20, 85)
        pregnancy_status = False
        pregnancy_trimester = None

    # Renal function (eGFR distribution)
    # 70% normal/mild, 20% moderate, 10% severe CKD
    r_val = random.random()
    if r_val < 0.55:
        egfr = round(random.uniform(90.0, 125.0), 1)
        ckd_stage = "Stage G1 (Normal)"
    elif r_val < 0.75:
        egfr = round(random.uniform(60.0, 89.0), 1)
        ckd_stage = "Stage G2 (Mildly decreased)"
    elif r_val < 0.88:
        egfr = round(random.uniform(45.0, 59.0), 1)
        ckd_stage = "Stage G3a (Mild-Moderate)"
    elif r_val < 0.95:
        egfr = round(random.uniform(30.0, 44.0), 1)
        ckd_stage = "Stage G3b (Moderate-Severe)"
    elif r_val < 0.98:
        egfr = round(random.uniform(15.0, 29.0), 1)
        ckd_stage = "Stage G4 (Severe)"
    else:
        egfr = round(random.uniform(8.0, 14.9), 1)
        ckd_stage = "Stage G5 (Kidney Failure)"

    # Hepatic impairment
    hep_val = random.random()
    if hep_val < 0.80:
        hepatic_impairment = "None"
    elif hep_val < 0.92:
        hepatic_impairment = "Mild"
    elif hep_val < 0.97:
        hepatic_impairment = "Moderate"
    else:
        hepatic_impairment = "Severe"

    # Number of medications (1 to 7)
    # Older patients or CKD patients tend to have polypharmacy
    if age >= 60 or "G3" in ckd_stage or "G4" in ckd_stage:
        num_meds = random.choices([2, 3, 4, 5, 6, 7], weights=[10, 20, 30, 25, 10, 5])[0]
    else:
        num_meds = random.choices([1, 2, 3, 4, 5], weights=[35, 35, 15, 10, 5])[0]

    # Select random medications from drugs pool
    selected_drugs = random.sample(drugs_pool, min(num_meds, len(drugs_pool))) if drugs_pool else []
    medications = []
    for d in selected_drugs:
        medications.append({
            "name": d["generic_name"],
            "dosage": "Standard therapeutic dose",
            "frequency": random.choice(["QD", "BID", "TID", "PRN"]),
            "route": "Oral",
            "drug_class": d.get("drug_class", "General Pharmaceutical")
        })

    # Comorbidities
    num_comorbidities = random.choices([0, 1, 2, 3, 4], weights=[20, 35, 25, 15, 5])[0]
    comorbidities = random.sample(COMMON_COMORBIDITIES, min(num_comorbidities, len(COMMON_COMORBIDITIES)))
    if "G3" in ckd_stage or "G4" in ckd_stage or "G5" in ckd_stage:
        if "Chronic Kidney Disease" not in comorbidities:
            comorbidities.append("Chronic Kidney Disease")

    # Allergy
    chosen_allergy = random.choice(COMMON_ALLERGIES)
    allergies = [chosen_allergy] if chosen_allergy != "None" else []

    # Component 1 upstream context
    anemia_tier = random.choices(["Low", "Moderate", "High"], weights=[30, 45, 25])[0]
    anemia_conf = round(random.uniform(0.72, 0.98), 2)

    return {
        "patient_id": patient_id,
        "age": age,
        "gender": gender,
        "pregnancy_status": pregnancy_status,
        "pregnancy_trimester": pregnancy_trimester,
        "current_medications": medications,
        "organ_function": {
            "egfr": egfr,
            "ckd_stage": ckd_stage,
            "hepatic_impairment": hepatic_impairment,
            "alt_ast_elevated": hepatic_impairment in ["Moderate", "Severe"],
        },
        "comorbidities": comorbidities,
        "allergies": allergies,
        "polypharmacy": len(medications) >= 5,
        "anemia_context": {
            "anemia_risk_tier": anemia_tier,
            "calibrated_confidence": anemia_conf,
            "source_component": "Component 1 (Reliability-Aware Screening)",
        }
    }


def main():
    random.seed(42)  # For scientific reproducibility
    drugs_pool = load_drugs_pool()
    print(f"Loaded {len(drugs_pool)} drugs from pharma_drugs.json")

    patient_cohort = []
    for i in range(1, 501):
        patient = generate_single_patient(i, drugs_pool)
        patient_cohort.append(patient)

    output_file = DATA_DIR / "synthetic_patients_500.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(patient_cohort, f, indent=2)

    print(f"Successfully generated {len(patient_cohort)} patient profiles at: {output_file}")


if __name__ == "__main__":
    main()
