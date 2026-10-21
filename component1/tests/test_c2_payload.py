"""Component 1 -> Component 2 adapter must satisfy C2's provisional contract (read-only import).

Run from repository root:
    python -m unittest component1.tests.test_c2_payload -v
"""

import sys
import unittest
from pathlib import Path

from component1.api.server import _c2_payload
from component1.fusion.reliability_fusion import fuse

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "component2"))
try:
    from app.models.c1_screening_payload import C1ScreeningPayload
except ImportError:  # Component 2 dependencies unavailable.
    C1ScreeningPayload = None


def report(regions, ppg, answers):
    profile = {"age_months": 300, "sex_reported_for_demo": "female", "pregnancy_status": "not_pregnant"}
    screening = fuse(regions, ppg, profile, answers, {})
    reliability = screening["reliability_aware_fusion"]
    return {
        "session_id": "demo_0000test",
        "modalities": {"images": {"regions": regions}, "ppg": ppg},
        "fusion": screening,
        "missing_inputs": [],
        "screening_result": {
            "risk_level": screening["experimental_risk_tier"],
            "reliability_score": reliability["reliability_score"],
            "decision_status": "experimental_tier_for_clinician_review",
        },
    }


@unittest.skipIf(C1ScreeningPayload is None, "Component 2 models not importable")
class C2Contract(unittest.TestCase):
    def test_empty_session_validates(self):
        payload = _c2_payload(report({}, {"available": False}, {}))
        model = C1ScreeningPayload.model_validate(payload)
        self.assertEqual(model.screening_result.risk_level, "insufficient_evidence")
        self.assertIsNone(model.screening_result.screening_confidence)
        self.assertEqual(model.modality_results.tongue.quality_status, "not_captured")

    def test_full_session_validates(self):
        regions = {
            "conjunctiva": {"captures": 1, "technical_passes": 1, "technical_pass_ratio": 1.0,
                            "cross_model_disagreement": False,
                            "model_votes": [{"source": "ghana_conjunctiva", "vote": 1, "score_uncalibrated": 0.8}],
                            "experimental_hb_estimates_g_dl": []},
            "nails": {"captures": 2, "technical_passes": 1, "technical_pass_ratio": 0.5,
                      "model_votes": [{"source": "ghana_fingernail", "vote": 1, "score_uncalibrated": 0.7}],
                      "experimental_hb_estimates_g_dl": [{"source": "yakimov_hb_2024", "estimate_g_dl": 11.2}]},
        }
        ppg = {"available": True, "quality_status": "retake_or_review",
               "quality_windows_passed": 1, "quality_windows_checked": 4}
        answers = {"C01": "yes", "C02": "yes", "C03": "no", "C06": "yes"}
        model = C1ScreeningPayload.model_validate(_c2_payload(report(regions, ppg, answers)))
        self.assertIn(model.screening_result.risk_level, {"low", "moderate", "high", "insufficient_evidence"})
        self.assertEqual(model.modality_results.ppg.signal_quality, 0.25)
        self.assertIn("fatigue", [s.name for s in model.symptoms if s.present])


if __name__ == "__main__":
    unittest.main()
