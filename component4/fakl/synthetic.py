"""SYNTHETIC test data for the FAKL prototype — illustrative, NOT clinical knowledge.

Claims use Component 2's Claim schema (claim_id, subject_id, predicate, object_id,
statement, confidence) and only relationship types its ontology allows
(component2/app/ontology/relationships.py). Feedback records mirror Component 2's
PractitionerFeedback (claim + review_outcome) plus the clinic_id that FAKL needs.

Component 2's real graph is currently empty, so this data stands in until it has
claims and clinic-tagged feedback.
"""

import numpy as np

DATA_LABEL = "SYNTHETIC (illustrative claims and feedback, not clinical knowledge)"

# (claim_id, subject_id, predicate, object_id, statement, prior confidence, hidden support)
# "hidden support" = share of practitioners who would agree; used ONLY to simulate votes.
CLAIM_TABLE = [
    ("CL-001", "SYM-PANDUTVA", "INDICATES", "ROGA-PANDU", "Pallor (Pandutva) indicates Pandu Roga", 0.70, 0.90),
    ("CL-002", "SYM-DAURBALYA", "INDICATES", "ROGA-PANDU", "Weakness (Daurbalya) indicates Pandu Roga", 0.60, 0.70),
    ("CL-003", "SYM-SHWASA", "INDICATES", "ROGA-PANDU", "Breathlessness (Shwasa) indicates Pandu Roga", 0.50, 0.65),
    ("CL-004", "SYM-BHRAMA", "INDICATES", "ROGA-PANDU", "Dizziness (Bhrama) indicates Pandu Roga", 0.55, 0.40),
    ("CL-005", "ROGA-PANDU", "ASSOCIATED_WITH_DOSHA", "DOSHA-PITTA", "Pandu Roga is associated with Pitta", 0.75, 0.85),
    ("CL-006", "ROGA-PANDU", "ASSOCIATED_WITH_DOSHA", "DOSHA-VATA", "Pandu Roga is associated with Vata", 0.50, 0.45),
    ("CL-007", "ROGA-PANDU", "ASSOCIATED_WITH_DOSHA", "DOSHA-KAPHA", "Pandu Roga is associated with Kapha", 0.50, 0.30),
    ("CL-008", "ROGA-PANDU", "AFFECTS_DHATU", "DHATU-RAKTA", "Pandu Roga affects Rakta Dhatu", 0.80, 0.90),
    ("CL-009", "ROGA-PANDU", "AFFECTS_DHATU", "DHATU-RASA", "Pandu Roga affects Rasa Dhatu", 0.60, 0.70),
    ("CL-010", "ROGA-PANDU", "SUGGESTS_PRINCIPLE", "TP-RAKTA-VARDHANA", "Pandu Roga suggests blood-nourishing therapy", 0.65, 0.80),
    ("CL-011", "ROGA-PANDU", "SUGGESTS_PRINCIPLE", "TP-LANGHANA", "Pandu Roga suggests fasting therapy (Langhana)", 0.50, 0.25),
    ("CL-012", "TP-RAKTA-VARDHANA", "RECOMMENDS_DIET", "DIET-IRON-RICH", "Blood-nourishing therapy recommends an iron-rich diet", 0.70, 0.85),
]

# Three clinics that differ (non-IID), like the model-training clinics:
#   activity      = average practitioner votes per claim
#   opinion_shift = how much more (or less) this clinic agrees than average
CLINICS = {
    1: {"name": "Estate-sector clinic", "activity": 8.0, "opinion_shift": +0.05},
    2: {"name": "Urban peripheral clinic", "activity": 5.0, "opinion_shift": -0.10},
    3: {"name": "Mixed rural clinic", "activity": 3.0, "opinion_shift": 0.00},
}

NEUTRAL_SHARE = 0.10   # share of feedback that is "uncertain" / "needs_more_evidence"


def claims():
    """{claim_id: prior confidence} — the graph's current values."""
    return {row[0]: row[5] for row in CLAIM_TABLE}


def claim_statements():
    return {row[0]: row[4] for row in CLAIM_TABLE}


def clinic_feedback(seed=7):
    """{clinic_id: [feedback records]} — each record is one practitioner's vote on one claim."""
    rng = np.random.default_rng(seed)
    feedback = {}
    for clinic_id, clinic in CLINICS.items():
        records = []
        for claim_id, *_, hidden_support in CLAIM_TABLE:
            p_agree = float(np.clip(hidden_support + clinic["opinion_shift"], 0.0, 1.0))
            for _ in range(rng.poisson(clinic["activity"])):
                if rng.random() < NEUTRAL_SHARE:
                    outcome = str(rng.choice(["uncertain", "needs_more_evidence"]))
                else:
                    outcome = "agree" if rng.random() < p_agree else "disagree"
                records.append({
                    "feedback_id": f"FB-{clinic_id}-{len(records) + 1:03d}",
                    "clinic_id": f"clinic-{clinic_id}",
                    "claim_id": claim_id,
                    "review_outcome": outcome,
                })
        feedback[clinic_id] = records
    return feedback
