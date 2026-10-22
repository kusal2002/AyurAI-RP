"""Unit tests for experimental reliability-aware fusion (no patient data, no I/O writes).

Run from repository root:
    python -m unittest component1.tests.test_reliability_fusion -v
"""

import csv
import unittest
from pathlib import Path

from component1.fusion import reliability_fusion as rf

REPO_ROOT = Path(__file__).resolve().parents[2]
ADULT_FEMALE = {"age_months": 300, "sex_reported_for_demo": "female", "pregnancy_status": "not_pregnant"}


def region(votes=(), hb=(), passes=1, captures=1):
    return {
        "captures": captures,
        "technical_passes": passes,
        "technical_pass_ratio": passes / captures,
        "model_votes": [{"source": s, "vote": int(v >= 0.5), "score_uncalibrated": v} for s, v in votes],
        "experimental_hb_estimates_g_dl": [{"source": s, "estimate_g_dl": v} for s, v in hb],
    }


def csv_row(relative, column, value):
    with open(REPO_ROOT / relative, encoding="utf-8") as handle:
        return next(row for row in csv.DictReader(handle) if row[column] == value)


class WeightsMatchEvaluationArtifacts(unittest.TestCase):
    def test_excluded_models_really_failed_their_baselines(self):
        cp = csv_row("component1/evaluation/images/efficientnet_test_metrics.csv", "Model", "EfficientNet-B0")
        self.assertLessEqual(float(cp["Test_AUROC"]), 0.5)
        tongue = csv_row("component1/evaluation/images/imagehb_tongue/heldout_test_metrics.csv", "model", "EfficientNet_B0")
        base = csv_row("component1/evaluation/images/imagehb_tongue/heldout_test_metrics.csv", "model", "Train_Mean_Hb_Baseline")
        self.assertGreater(float(tongue["test_MAE_g_dl"]), float(base["test_MAE_g_dl"]))
        ppg = csv_row("component1/evaluation/ppg/max30102_heldout_test_metrics.csv", "model", "Ridge")
        ppg_base = csv_row("component1/evaluation/ppg/max30102_heldout_test_metrics.csv", "model", "Training mean Hb")
        self.assertGreater(float(ppg["test_MAE_g_dl"]), float(ppg_base["test_MAE_g_dl"]))
        for source in ("cp_anemic_v2", "imagehb_sample", "max30102_ppg_ridge"):
            self.assertEqual(rf.SOURCE_RELIABILITY[source]["weight"], 0.0)

    def test_nail_classifier_weight_from_balanced_accuracy(self):
        row = csv_row("component1/evaluation/images/ghana_fingernail/test_metrics.csv", "Model", "ResNet-50")
        expected = (float(row["Balanced_Accuracy"]) - 0.5) / 0.5
        self.assertAlmostEqual(rf.SOURCE_RELIABILITY["ghana_fingernail"]["weight"], expected, places=2)

    def test_yakimov_weight_is_halved_validation_improvement(self):
        row = csv_row("component1/evaluation/images/yakimov_hb_2024/validation_comparison.csv", "Model", "efficientnet_b0")
        expected = 0.5 * (1 - float(row["Val_MAE_g_dl"]) / float(row["Naive_Val_MAE_g_dl"]))
        self.assertAlmostEqual(rf.SOURCE_RELIABILITY["yakimov_hb_2024"]["weight"], expected, places=3)


class WhoThresholds(unittest.TestCase):
    def test_groups(self):
        self.assertEqual(rf.who_hb_threshold(ADULT_FEMALE)[0], 12.0)
        self.assertEqual(rf.who_hb_threshold({"age_months": 300, "sex": "male"})[0], 13.0)
        self.assertEqual(rf.who_hb_threshold({"age_months": 300, "pregnancy_status": "pregnant"})[0], 11.0)
        self.assertEqual(rf.who_hb_threshold({"age_months": 36})[0], 11.0)
        self.assertEqual(rf.who_hb_threshold({"age_months": 100})[0], 11.5)
        self.assertEqual(rf.who_hb_threshold({"age_months": 170})[0], 12.0)
        self.assertIsNone(rf.who_hb_threshold({"age_months": 3})[0])
        self.assertIsNone(rf.who_hb_threshold({"age_months": 300})[0])


class Questionnaire(unittest.TestCase):
    def test_too_few_answers_is_unusable(self):
        self.assertFalse(rf.questionnaire_evidence({"C01": "yes", "C02": "not_sure"})["usable"])

    def test_symptom_fraction(self):
        result = rf.questionnaire_evidence({"C01": "yes", "C02": "yes", "C03": "no", "C06": "yes"})
        self.assertTrue(result["usable"])
        self.assertAlmostEqual(result["evidence"], 0.5)
        self.assertFalse(result["trained_model"])

    def test_pandu_type_signs_never_change_the_symptom_fraction(self):
        core = {"C01": "yes", "C02": "yes", "C03": "no", "C06": "yes"}
        result = rf.questionnaire_evidence({**core, "PT04": "yes", "PT05": "yes", "PT11": "no"})
        self.assertEqual(result["evidence"], rf.questionnaire_evidence(core)["evidence"])
        self.assertEqual(result["answered_items"], 4)
        self.assertEqual(result["pandu_type_signs_present"], ["burning_sensation", "excessive_thirst"])
        self.assertEqual(result["pandu_type_signs_absent"], ["cough"])
        self.assertNotIn("burning_sensation", result["present_symptoms"])


class Fusion(unittest.TestCase):
    def test_no_evidence_is_insufficient(self):
        result = rf.fuse({}, {"available": False}, ADULT_FEMALE, {}, {})
        self.assertEqual(result["experimental_risk_tier"], "insufficient_evidence")
        self.assertEqual(result["conventional_fusion"]["tier"], "insufficient_evidence")

    def test_single_modality_is_insufficient(self):
        regions = {"nails": region(votes=[("ghana_fingernail", 0.9)], hb=[("yakimov_hb_2024", 9.0)])}
        result = rf.fuse(regions, {"available": False}, ADULT_FEMALE, {}, {})
        self.assertEqual(result["experimental_risk_tier"], "insufficient_evidence")
        self.assertIn("physiological", " ".join(result["reliability_aware_fusion"]["insufficient_reasons"]))

    def test_excluded_models_never_drive_the_tier(self):
        regions = {
            "conjunctiva": region(votes=[("cp_anemic_v2", 0.99)]),
            "tongue": region(hb=[("imagehb_sample", 7.0)]),
        }
        result = rf.fuse(regions, {"available": False}, ADULT_FEMALE, {}, {})
        self.assertEqual(result["experimental_risk_tier"], "insufficient_evidence")
        self.assertEqual(result["conventional_fusion"]["tier"], "high")

    def test_agreeing_sources_give_high(self):
        regions = {
            "conjunctiva": region(votes=[("ghana_conjunctiva", 0.95)]),
            "nails": region(votes=[("ghana_fingernail", 0.9)]),
        }
        result = rf.fuse(regions, {"available": False}, ADULT_FEMALE, {}, {})
        self.assertEqual(result["experimental_risk_tier"], "high")
        self.assertFalse(result["reliability_aware_fusion"]["reliability_score_is_probability"])

    def test_conflict_gives_insufficient(self):
        regions = {
            "conjunctiva": region(votes=[("ghana_conjunctiva", 0.95)]),
            "nails": region(votes=[("ghana_fingernail", 0.02)]),
        }
        result = rf.fuse(regions, {"available": False}, ADULT_FEMALE, {}, {})
        self.assertEqual(result["experimental_risk_tier"], "insufficient_evidence")

    def test_failed_quality_removes_weight(self):
        regions = {
            "conjunctiva": region(votes=[("ghana_conjunctiva", 0.95)], passes=0),
            "nails": region(votes=[("ghana_fingernail", 0.9)]),
        }
        result = rf.fuse(regions, {"available": False}, ADULT_FEMALE, {}, {})
        self.assertEqual(result["experimental_risk_tier"], "insufficient_evidence")

    def test_safety_flags(self):
        status = {"urgent_clinician_review": True, "urgent_response_ids": ["SAF01"], "ppg_acquisition_allowed": False}
        result = rf.fuse({}, {"available": True}, ADULT_FEMALE, {}, status)
        self.assertEqual(len(result["safety_flags"]), 2)
        self.assertTrue(result["doctor_review_recommendations"][0].startswith("Immediate"))


if __name__ == "__main__":
    unittest.main()
