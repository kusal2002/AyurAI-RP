"""AyurAI Component 1: experimental reliability-aware evidence fusion (v2).

Pure functions only; fuse_screening_session.py supplies session evidence.

Every rule and weight below is PRE-SPECIFIED and UNVALIDATED:
- No dataset contains all modalities from the same participants, so the fused
  tier has no measured accuracy.
- The reliability score is a transparent heuristic in [0, 1]; it is NOT a
  calibrated probability of anaemia or of a correct result.
- The output is research evidence for clinician review, never a diagnosis.
"""

from __future__ import annotations

from statistics import mean

FUSION_VERSION = "c1.fusion.v2-experimental"

# Held-out performance -> performance weight (0 = shown but ignored).
# Classification: weight = (balanced accuracy - 0.5) / 0.5, 0 if AUROC <= 0.5.
# Hb regression:  weight = 1 - model MAE / mean-baseline MAE (0 if negative),
#                 halved when only validation (no held-out test) exists.
SOURCE_RELIABILITY = {
    "cp_anemic_v2": {
        "region": "conjunctiva", "task": "classification", "weight": 0.0,
        "basis": "Held-out AUROC 0.474 (<= 0.5); excluded from weighting",
        "evidence_file": "component1/evaluation/images/efficientnet_test_metrics.csv",
    },
    "ghana_conjunctiva": {
        "region": "conjunctiva", "task": "classification", "weight": 0.28,
        "basis": "Held-out balanced accuracy 0.64 (recall 0.43, specificity 0.85; 78 images)",
        "evidence_file": "component1/evaluation/images/ghana_conjunctiva/test_classification_report.txt",
    },
    "ghana_fingernail": {
        "region": "nails", "task": "classification", "weight": 0.21,
        "basis": "Held-out balanced accuracy 0.606 (84 images)",
        "evidence_file": "component1/evaluation/images/ghana_fingernail/test_metrics.csv",
    },
    "yakimov_hb_2024": {
        "region": "nails", "task": "hb_regression", "weight": 0.066,
        "basis": "Validation MAE 1.284 vs naive 1.479 g/dL; no held-out test (weight halved)",
        "evidence_file": "component1/evaluation/images/yakimov_hb_2024/validation_comparison.csv",
    },
    "imagehb_sample": {
        "region": "tongue", "task": "hb_regression", "weight": 0.0,
        "basis": "Held-out MAE 1.224 vs mean baseline 1.164 g/dL (worse than baseline); excluded",
        "evidence_file": "component1/evaluation/images/imagehb_tongue/heldout_test_metrics.csv",
    },
    "max30102_ppg_ridge": {
        "region": "ppg", "task": "hb_regression", "weight": 0.0,
        "basis": "Held-out MAE 1.694 vs mean baseline 1.614 g/dL; live transfer unverified",
        "evidence_file": "component1/evaluation/ppg/max30102_heldout_test_metrics.csv",
    },
}

# Rule-based questionnaire evidence (not a trained model).
QUESTIONNAIRE_WEIGHT = 0.10
SYMPTOM_ITEMS = {
    "C01": "fatigue_or_weakness",
    "C02": "breathlessness_on_exertion",
    "C03": "dizziness_or_faintness",
    "C04": "palpitations",
    "C05": "frequent_headaches",
    "C06": "reported_pallor",
    "C07": "cold_hands_or_feet",
    "C08": "previous_anaemia_or_low_hb",
    "C10": "recent_or_recurring_blood_loss",
    "BL03": "blood_in_stool_or_urine",
    "MEN01": "heavy_or_prolonged_menstruation",
}
MIN_ANSWERED_SYMPTOMS = 3

# Decision rules.
MIN_TOTAL_RELIABILITY = 0.40
MIN_PHYSIOLOGICAL_MODALITIES = 2
CONFLICT_RATIO = 0.35
HIGH_SCORE = 0.40
MODERATE_SCORE = 0.10
HB_EVIDENCE_SCALE_G_DL = 2.0

TIERS = ("low", "moderate", "high", "insufficient_evidence")


def clip(value, low=-1.0, high=1.0):
    return max(low, min(high, value))


def who_hb_threshold(profile: dict) -> tuple[float | None, str]:
    """WHO (2011) Hb cut-off for anaemia in g/dL, by age, sex and pregnancy."""
    age = profile.get("age_months")
    if not isinstance(age, int) or isinstance(age, bool) or age < 6:
        return None, "age missing or under 6 months: no WHO cut-off applied"
    if profile.get("pregnancy_status") == "pregnant":
        return 11.0, "WHO pregnant women: Hb < 11.0 g/dL"
    if age < 60:
        return 11.0, "WHO children 6-59 months: Hb < 11.0 g/dL"
    if age < 144:
        return 11.5, "WHO children 5-11 years: Hb < 11.5 g/dL"
    if age < 180:
        return 12.0, "WHO children 12-14 years: Hb < 12.0 g/dL"
    sex = str(profile.get("sex") or profile.get("sex_reported_for_demo") or "").lower()
    if sex == "female":
        return 12.0, "WHO non-pregnant women >= 15 years: Hb < 12.0 g/dL"
    if sex == "male":
        return 13.0, "WHO men >= 15 years: Hb < 13.0 g/dL"
    return None, "sex not recorded for adult: no WHO cut-off applied"


def questionnaire_evidence(answers: dict) -> dict:
    """Fraction of answered anaemia-related symptoms reported present."""
    answered = {qid: answers[qid] for qid in SYMPTOM_ITEMS if answers.get(qid) in ("yes", "no")}
    present = [SYMPTOM_ITEMS[qid] for qid, value in answered.items() if value == "yes"]
    absent = [SYMPTOM_ITEMS[qid] for qid, value in answered.items() if value == "no"]
    usable = len(answered) >= MIN_ANSWERED_SYMPTOMS
    fraction = len(present) / len(answered) if answered else None
    return {
        "method": "rule_based_symptom_fraction",
        "trained_model": False,
        "answered_items": len(answered),
        "present_symptoms": present,
        "absent_symptoms": absent,
        "symptom_fraction": round(fraction, 3) if fraction is not None else None,
        "usable": usable,
        "evidence": round(2 * fraction - 1, 3) if usable else None,
    }


def evidence_items(regions: dict, ppg: dict, questionnaire: dict | None, threshold: float | None) -> list[dict]:
    """One item per (modality, model source); evidence in [-1, 1], + = towards anaemia."""
    items = []
    for region, info in regions.items():
        quality = info.get("technical_pass_ratio", 0.0)
        by_source: dict[str, dict] = {}
        for vote in info.get("model_votes", []):
            score = vote.get("score_uncalibrated")
            if isinstance(score, (int, float)):
                by_source.setdefault(vote["source"], {"task": "classification", "values": []})["values"].append(score)
        for estimate in info.get("experimental_hb_estimates_g_dl", []):
            value = estimate.get("estimate_g_dl")
            if isinstance(value, (int, float)):
                by_source.setdefault(estimate["source"], {"task": "hb_regression", "values": []})["values"].append(value)

        for source, entry in by_source.items():
            meta = SOURCE_RELIABILITY.get(source, {"weight": 0.0, "basis": "No held-out evaluation registered"})
            raw = mean(entry["values"])
            if entry["task"] == "classification":
                evidence = clip(2 * raw - 1)
                conventional_vote = int(raw >= 0.5)
                note = None
            elif threshold is not None:
                evidence = clip((threshold - raw) / HB_EVIDENCE_SCALE_G_DL)
                conventional_vote = int(raw < threshold)
                note = None
            else:
                evidence, conventional_vote, note = None, None, "No WHO Hb cut-off for this profile"
            weight = round(meta["weight"] * quality, 3) if evidence is not None else 0.0
            items.append({
                "modality": region,
                "source": source,
                "task": entry["task"],
                "outputs": len(entry["values"]),
                "mean_output": round(raw, 3),
                "evidence": round(evidence, 3) if evidence is not None else None,
                "technical_pass_ratio": quality,
                "performance_weight": meta["weight"],
                "reliability_weight": weight,
                "weight_basis": meta["basis"],
                "conventional_vote": conventional_vote,
                **({"note": note} if note else {}),
            })

    if ppg.get("available"):
        items.append({
            "modality": "ppg", "source": "max30102_ppg_ridge", "task": "hb_regression",
            "outputs": 0, "mean_output": None, "evidence": None,
            "technical_pass_ratio": None, "performance_weight": 0.0, "reliability_weight": 0.0,
            "weight_basis": SOURCE_RELIABILITY["max30102_ppg_ridge"]["basis"],
            "conventional_vote": None,
            "note": "PPG recorded; Hb model not applied to live data. HR/SpO2 are not anaemia evidence.",
        })

    if questionnaire and questionnaire.get("usable"):
        items.append({
            "modality": "questionnaire", "source": "symptom_rules_v1", "task": "rule_based",
            "outputs": questionnaire["answered_items"], "mean_output": questionnaire["symptom_fraction"],
            "evidence": questionnaire["evidence"], "technical_pass_ratio": None,
            "performance_weight": QUESTIONNAIRE_WEIGHT, "reliability_weight": QUESTIONNAIRE_WEIGHT,
            "weight_basis": "Expert-specified symptom rule; not trained or validated",
            "conventional_vote": int(questionnaire["symptom_fraction"] >= 0.5),
        })
    return items


def score_to_tier(score: float) -> str:
    if score >= HIGH_SCORE:
        return "high"
    if score >= MODERATE_SCORE:
        return "moderate"
    return "low"


def conventional_fusion(items: list[dict]) -> dict:
    """Baseline: equal-weight majority vote of every available output, no quality or reliability gating."""
    votes = [item["conventional_vote"] for item in items if item["conventional_vote"] is not None]
    if not votes:
        return {"method": "equal_weight_majority_vote", "votes": 0, "anaemia_vote_fraction": None, "tier": "insufficient_evidence"}
    fraction = sum(votes) / len(votes)
    tier = "high" if fraction >= 2 / 3 else "moderate" if fraction >= 1 / 3 else "low"
    return {"method": "equal_weight_majority_vote", "votes": len(votes),
            "anaemia_vote_fraction": round(fraction, 3), "tier": tier}


def reliability_aware_fusion(items: list[dict]) -> dict:
    usable = [item for item in items if item["reliability_weight"] > 0 and item["evidence"] is not None]
    total = sum(item["reliability_weight"] for item in usable)
    physiological = sorted({item["modality"] for item in usable if item["modality"] != "questionnaire"})
    toward = sum(item["reliability_weight"] for item in usable if item["evidence"] > 0.2)
    against = sum(item["reliability_weight"] for item in usable if item["evidence"] < -0.2)
    conflict_ratio = min(toward, against) / (toward + against) if toward + against else 0.0
    score = sum(item["reliability_weight"] * item["evidence"] for item in usable) / total if total else None

    reasons = []
    if total < MIN_TOTAL_RELIABILITY:
        reasons.append(f"total reliability {total:.2f} < {MIN_TOTAL_RELIABILITY}")
    if len(physiological) < MIN_PHYSIOLOGICAL_MODALITIES:
        reasons.append(f"{len(physiological)} usable physiological modality(ies) < {MIN_PHYSIOLOGICAL_MODALITIES}")
    if conflict_ratio > CONFLICT_RATIO:
        reasons.append(f"weighted evidence conflict {conflict_ratio:.2f} > {CONFLICT_RATIO}")

    return {
        "method": "quality_and_heldout_performance_weighted_mean",
        "usable_sources": [f"{item['modality']}:{item['source']}" for item in usable],
        "excluded_sources": [f"{item['modality']}:{item['source']}" for item in items if item not in usable],
        "usable_physiological_modalities": physiological,
        "weighted_evidence_score": round(score, 3) if score is not None else None,
        "reliability_score": round(min(total, 1.0), 3),
        "reliability_score_is_probability": False,
        "conflict_ratio": round(conflict_ratio, 3),
        "insufficient_reasons": reasons,
        "tier": "insufficient_evidence" if reasons or score is None else score_to_tier(score),
    }


def fuse(regions: dict, ppg: dict, profile: dict, answers: dict, status: dict) -> dict:
    """Return the v2 experimental screening block for one session."""
    threshold, threshold_basis = who_hb_threshold(profile)
    symptoms = questionnaire_evidence(answers) if answers else None
    items = evidence_items(regions, ppg, symptoms, threshold)
    conventional = conventional_fusion(items)
    reliability = reliability_aware_fusion(items)

    safety_flags = []
    if status.get("urgent_clinician_review"):
        safety_flags.append("Urgent safety answer(s): " + ", ".join(status.get("urgent_response_ids", [])))
    if ppg.get("available") and status and status.get("ppg_acquisition_allowed") is False:
        safety_flags.append("PPG was recorded although the questionnaire had not cleared PPG acquisition")
    if regions and status and status.get("image_acquisition_allowed") is False:
        safety_flags.append("Images were captured although the questionnaire had not cleared image acquisition")

    tier = reliability["tier"]
    rationale = []
    for item in items:
        if item["reliability_weight"] > 0:
            direction = "towards anaemia" if item["evidence"] > 0.2 else "against anaemia" if item["evidence"] < -0.2 else "neutral"
            rationale.append(f"{item['modality']} / {item['source']}: evidence {item['evidence']:+.2f} ({direction}), weight {item['reliability_weight']:.3f}")
        else:
            rationale.append(f"{item['modality']} / {item['source']}: shown, not weighted ({item.get('note') or item['weight_basis']})")
    if reliability["insufficient_reasons"]:
        rationale.append("Insufficient evidence: " + "; ".join(reliability["insufficient_reasons"]))

    recommendations = ["Confirm with laboratory haemoglobin / CBC before any clinical decision."]
    if safety_flags and status.get("urgent_clinician_review"):
        recommendations.insert(0, "Immediate clinician assessment for urgent safety answer(s).")
    if tier == "insufficient_evidence":
        recommendations.append("Repeat or complete captures for missing or low-reliability modalities.")
    elif tier == "high":
        recommendations.append("Prioritise clinician review and laboratory Hb testing.")
    if conventional["tier"] != tier:
        recommendations.append(f"Conventional fusion would report '{conventional['tier']}'; review why sources were down-weighted.")

    return {
        "fusion_version": FUSION_VERSION,
        "experimental_risk_tier": tier,
        "tier_is_validated": False,
        "hb_threshold_g_dl": threshold,
        "hb_threshold_basis": threshold_basis,
        "questionnaire_evidence": symptoms,
        "evidence_items": items,
        "conventional_fusion": conventional,
        "reliability_aware_fusion": reliability,
        "rationale": rationale,
        "safety_flags": safety_flags,
        "doctor_review_recommendations": recommendations,
        "decision_rules": {
            "min_total_reliability": MIN_TOTAL_RELIABILITY,
            "min_physiological_modalities": MIN_PHYSIOLOGICAL_MODALITIES,
            "max_conflict_ratio": CONFLICT_RATIO,
            "high_score_at_least": HIGH_SCORE,
            "moderate_score_at_least": MODERATE_SCORE,
            "hb_evidence_scale_g_dl": HB_EVIDENCE_SCALE_G_DL,
            "status": "pre-specified, unvalidated",
        },
    }
