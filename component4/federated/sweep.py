"""Run every experiment from the proposal and summarise the results.

Grid: 2 strategies (FedAvg, FedProx) x 5 ε values x N runs (default 3).
Each run writes results/<strategy>_eps<ε>_run<n>.csv (via run.py).
Afterwards this script writes results/summary.csv with the mean and
standard deviation of the final-round accuracy for each (strategy, ε).

Usage:  python component4/federated/sweep.py [--runs 3]
"""

import argparse
import csv
import statistics
import subprocess
import sys
from pathlib import Path

from config import EPSILONS, NUM_ROUNDS
from data import DATA_SOURCE

HERE = Path(__file__).resolve().parent
RUN_SCRIPT = str(HERE / "run.py")
RESULTS_DIR = HERE.parent / "results"
STRATEGIES = ["fedavg", "fedprox"]


def final_row(csv_path):
    """Return the last round's row of one run's CSV as a dict."""
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))[-1]


def summarise(runs):
    rows = []
    for strategy in STRATEGIES:
        for eps in EPSILONS:
            finals = [final_row(RESULTS_DIR / f"{strategy}_eps{eps}_run{r}.csv") for r in range(1, runs + 1)]
            accuracies = [float(row["accuracy"]) for row in finals]
            rows.append({
                "strategy": strategy,
                "target_epsilon": eps,
                "runs": runs,
                "rounds": NUM_ROUNDS,
                "final_accuracy_mean": statistics.mean(accuracies),
                "final_accuracy_std": statistics.stdev(accuracies) if runs > 1 else 0.0,
                "epsilon_spent_max": max(float(row["epsilon_spent"]) for row in finals),
                "data_source": DATA_SOURCE,
            })

    summary_path = RESULTS_DIR / "summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full FedAvg/FedProx x ε grid")
    parser.add_argument("--runs", type=int, default=3, help="repeats per setting (proposal: 3)")
    args = parser.parse_args()

    for strategy in STRATEGIES:
        for eps in EPSILONS:
            for run in range(1, args.runs + 1):
                # check=True stops the sweep immediately if a run fails
                subprocess.run(
                    [sys.executable, RUN_SCRIPT, str(eps), "--strategy", strategy, "--run", str(run)],
                    check=True,
                )

    summarise(args.runs)
