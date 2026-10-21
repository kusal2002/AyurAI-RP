"""Tests for the FAKL prototype algorithm (component4/fakl/algorithm.py).

Run from the repository root:
    python -m unittest discover component4/tests -v
"""

import statistics
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fakl"))

from algorithm import (  # noqa: E402
    centralised_update,
    federated_update,
    local_update,
    mean_abs_difference,
    updated_confidence,
)
from synthetic import claims, clinic_feedback  # noqa: E402


def vote(claim_id, outcome):
    return {"claim_id": claim_id, "review_outcome": outcome}


class FaklTests(unittest.TestCase):
    def setUp(self):
        self.prior = claims()
        self.feedback = clinic_feedback()
        self.pooled = [record for records in self.feedback.values() for record in records]

    def test_federated_without_privacy_equals_centralised(self):
        """Core property: combining per-clinic counts == pooling all raw feedback."""
        shares = [local_update(records) for records in self.feedback.values()]
        federated = federated_update(self.prior, shares)
        central = centralised_update(self.prior, self.pooled)
        for claim_id in self.prior:
            self.assertAlmostEqual(federated[claim_id], central[claim_id], places=12)

    def test_only_counts_leave_a_clinic(self):
        """A clinic's share holds two numbers per claim: no ids, outcomes, text or reviewers."""
        share = local_update(self.feedback[1])
        for claim_id, value in share.items():
            self.assertIn(claim_id, self.prior)
            self.assertEqual(len(value), 2)
            self.assertTrue(all(isinstance(number, float) for number in value))

    def test_claim_without_feedback_keeps_its_confidence(self):
        result = federated_update({"CL-X": 0.42}, [{}, {}, {}])
        self.assertAlmostEqual(result["CL-X"], 0.42)

    def test_claim_without_confidence_starts_neutral(self):
        """Component 2 creates claims with confidence=None; FAKL starts them at 0.5."""
        self.assertAlmostEqual(federated_update({"CL-NEW": None}, [{}])["CL-NEW"], 0.5)
        agrees = local_update([vote("CL-NEW", "agree")] * 6)
        self.assertGreater(federated_update({"CL-NEW": None}, [agrees])["CL-NEW"], 0.5)
        central = centralised_update({"CL-NEW": None}, [vote("CL-NEW", "agree")] * 6)
        self.assertAlmostEqual(central["CL-NEW"], federated_update({"CL-NEW": None}, [agrees])["CL-NEW"])

    def test_neutral_feedback_does_not_move_confidence(self):
        share = local_update([vote("CL-X", "uncertain"), vote("CL-X", "needs_more_evidence")])
        self.assertAlmostEqual(federated_update({"CL-X": 0.42}, [share])["CL-X"], 0.42)

    def test_agreement_raises_and_disagreement_lowers_confidence(self):
        self.assertGreater(updated_confidence(0.5, agree=8, disagree=0), 0.5)
        self.assertLess(updated_confidence(0.5, agree=0, disagree=8), 0.5)

    def test_small_counts_are_suppressed(self):
        two_votes = [vote("CL-X", "agree"), vote("CL-X", "disagree")]
        self.assertNotIn("CL-X", local_update(two_votes, min_votes=3))
        self.assertIn("CL-X", local_update(two_votes, min_votes=2))

    def test_confidences_stay_between_0_and_1(self):
        rng = np.random.default_rng(0)
        shares = [local_update(records, min_votes=3, epsilon=0.5, rng=rng) for records in self.feedback.values()]
        for value in federated_update(self.prior, shares).values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_more_privacy_budget_means_closer_to_centralised(self):
        """DP noise shrinks as ε grows (averaged over repeats, fixed seeds)."""
        central = centralised_update(self.prior, self.pooled)

        def mean_gap(epsilon):
            gaps = []
            for seed in range(30):
                rng = np.random.default_rng(seed)
                shares = [local_update(r, epsilon=epsilon, rng=rng) for r in self.feedback.values()]
                gaps.append(mean_abs_difference(federated_update(self.prior, shares), central))
            return statistics.mean(gaps)

        self.assertGreater(mean_gap(0.5), mean_gap(2.0))
        self.assertGreater(mean_gap(2.0), mean_gap(5.0))


if __name__ == "__main__":
    unittest.main()
