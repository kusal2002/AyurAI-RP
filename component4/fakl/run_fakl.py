"""Run the FAKL prototype on synthetic data and compare it with centralised pooling.

Usage:  python component4/fakl/run_fakl.py
Writes  component4/results/fakl_summary.csv  (one row per setting)
        component4/results/fakl_claims.csv   (per-claim confidences)

Settings compared (all against centralised pooling of every clinic's raw feedback):
  - federated, no privacy                  -> should match exactly
  - federated + suppression (min votes)    -> claims with little feedback stay closer to the prior
  - federated + differential privacy (ε)   -> noise; the gap should shrink as ε grows
"""

import csv
import statistics
from pathlib import Path

import numpy as np

from algorithm import centralised_update, federated_update, local_update, mean_abs_difference
from synthetic import DATA_LABEL, claim_statements, claims, clinic_feedback

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
EPSILONS = [0.5, 1.0, 2.0, 5.0]
MIN_VOTES = 3          # suppression threshold used in the privacy settings
NOISE_REPEATS = 30     # DP noise is random: average over this many runs


def run_federated(prior, feedback, min_votes=0, epsilon=None, seed=0):
    """Each clinic runs local_update on ITS OWN feedback; the server only sees the shares."""
    rng = np.random.default_rng(seed)
    shares = [local_update(records, min_votes=min_votes, epsilon=epsilon, rng=rng)
              for records in feedback.values()]
    return federated_update(prior, shares), shares


if __name__ == "__main__":
    prior = claims()
    feedback = clinic_feedback()
    all_feedback = [record for records in feedback.values() for record in records]
    central = centralised_update(prior, all_feedback)

    rows = []

    federated, shares = run_federated(prior, feedback)
    rows.append({"setting": "federated, no privacy", "epsilon": "", "min_votes": 0,
                 "mean_abs_diff": mean_abs_difference(federated, central), "std": 0.0,
                 "values_shared_per_clinic": statistics.mean(2 * len(s) for s in shares)})

    suppressed, shares = run_federated(prior, feedback, min_votes=MIN_VOTES)
    rows.append({"setting": "federated + suppression", "epsilon": "", "min_votes": MIN_VOTES,
                 "mean_abs_diff": mean_abs_difference(suppressed, central), "std": 0.0,
                 "values_shared_per_clinic": statistics.mean(2 * len(s) for s in shares)})

    dp_example = None
    for eps in EPSILONS:
        gaps, shared = [], []
        for repeat in range(NOISE_REPEATS):
            result, shares = run_federated(prior, feedback, min_votes=MIN_VOTES, epsilon=eps, seed=repeat)
            gaps.append(mean_abs_difference(result, central))
            shared.append(statistics.mean(2 * len(s) for s in shares))
            if eps == 1.0 and repeat == 0:
                dp_example = result
        rows.append({"setting": "federated + suppression + DP", "epsilon": eps, "min_votes": MIN_VOTES,
                     "mean_abs_diff": statistics.mean(gaps), "std": statistics.stdev(gaps),
                     "values_shared_per_clinic": statistics.mean(shared)})

    RESULTS_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / "fakl_summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) + ["data"])
        writer.writeheader()
        writer.writerows({**row, "data": DATA_LABEL} for row in rows)

    statements = claim_statements()
    with open(RESULTS_DIR / "fakl_claims.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["claim_id", "statement", "prior", "centralised", "federated",
                         "federated_suppression", "federated_dp_eps1", "data"])
        for claim_id in prior:
            writer.writerow([claim_id, statements[claim_id], prior[claim_id], round(central[claim_id], 4),
                             round(federated[claim_id], 4), round(suppressed[claim_id], 4),
                             round(dp_example[claim_id], 4), DATA_LABEL])

    print(f"Data: {DATA_LABEL}")
    print(f"Feedback records: {len(all_feedback)} across {len(feedback)} clinics (never pooled by FAKL)\n")
    print(f"{'setting':32s} {'ε':>4s}  gap to centralised (mean ± std)   values shared per clinic")
    for row in rows:
        eps = str(row["epsilon"]) if row["epsilon"] != "" else "—"
        print(f"{row['setting']:32s} {eps:>4s}  {row['mean_abs_diff']:.4f} ± {row['std']:.4f}"
              f"                {row['values_shared_per_clinic']:.1f}")
    print(f"\nSaved {RESULTS_DIR / 'fakl_summary.csv'} and {RESULTS_DIR / 'fakl_claims.csv'}")
