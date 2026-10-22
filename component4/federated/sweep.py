"""Run every experiment from the proposal and summarise the results.

Grid: 2 strategies (FedAvg, FedProx) x 5 ε values x N runs (default 3).
Each run writes results/<strategy>_eps<ε>_run<n>.csv (via run.py).
Writes results/summary.csv: mean and standard deviation of the final-round
accuracy and macro-F1 for each (strategy, ε), and results/clinic_counts.csv:
patients per risk tier at each clinic (aggregate counts only, never the data).

Reference points (written to results/baselines.csv), to read the grid against:
  - majority class and centralised training without DP   (centralized.py)
  - federated training WITHOUT DP, per strategy          (run.py --no-dp)
so a drop in accuracy can be attributed to federation or to the DP noise.

Usage:  python component4/federated/sweep.py [--runs 3]
"""

import argparse
import csv
import statistics
import subprocess
import sys
from pathlib import Path

from config import CLINIC_PROFILES, EPSILONS, FEATURES_FILE, NUM_ROUNDS
from data import DATA_SOURCE, USE_REAL_DATA

HERE = Path(__file__).resolve().parent
RUN_SCRIPT = str(HERE / "run.py")
CENTRALIZED_SCRIPT = str(HERE / "centralized.py")
RESULTS_DIR = HERE.parent / "results"
STRATEGIES = ["fedavg", "fedprox"]


def final_row(csv_path):
    """Return the last round's row of one run's CSV as a dict."""
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))[-1]


def mean_std(values):
    return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def summarise(runs):
    rows = []
    for strategy in STRATEGIES:
        for eps in EPSILONS:
            finals = [final_row(RESULTS_DIR / f"{strategy}_eps{eps}_run{r}.csv") for r in range(1, runs + 1)]
            acc_mean, acc_std = mean_std([float(row["accuracy"]) for row in finals])
            f1_mean, f1_std = mean_std([float(row["macro_f1"]) for row in finals])
            rows.append({
                "strategy": strategy,
                "target_epsilon": eps,
                "runs": runs,
                "rounds": NUM_ROUNDS,
                "final_accuracy_mean": acc_mean,
                "final_accuracy_std": acc_std,
                "final_macro_f1_mean": f1_mean,
                "final_macro_f1_std": f1_std,
                "epsilon_spent_max": max(float(row["epsilon_spent"]) for row in finals),
                "data_source": DATA_SOURCE,
            })

    summary_path = RESULTS_DIR / "summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved summary to {summary_path}")


def save_clinic_counts():
    """Patients per risk tier at each clinic -> results/clinic_counts.csv.

    Only these aggregate counts are committed (the dataset never is), so a server
    without the dataset, such as the deployed dashboard, can still show the real split."""
    if not USE_REAL_DATA:
        return  # placeholder counts are already in config.py
    counts = {clinic_id: [0, 0, 0] for clinic_id in CLINIC_PROFILES}   # [low, moderate, high]
    with open(FEATURES_FILE, newline="") as f:
        for row in csv.DictReader(f):
            counts[int(row["clinic_id"])][int(row["tier"])] += 1

    path = RESULTS_DIR / "clinic_counts.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["clinic_id", "low", "moderate", "high", "data_source"])
        for clinic_id, (low, moderate, high) in counts.items():
            writer.writerow([clinic_id, low, moderate, high, DATA_SOURCE])
    print(f"Saved clinic counts to {path}")


def summarise_baselines(runs):
    """Combine centralized.csv with the no-DP federated runs into baselines.csv."""
    rows = []
    with open(RESULTS_DIR / "centralized.csv", newline="") as f:
        for row in csv.DictReader(f):
            rows.append({"method": row["method"], "accuracy_mean": row["accuracy_mean"],
                         "accuracy_std": row["accuracy_std"], "macro_f1_mean": row["macro_f1_mean"],
                         "runs": row["runs"]})
    for strategy in STRATEGIES:
        finals = [final_row(RESULTS_DIR / f"{strategy}_nodp_run{r}.csv") for r in range(1, runs + 1)]
        acc_mean, acc_std = mean_std([float(row["accuracy"]) for row in finals])
        f1_mean, _ = mean_std([float(row["macro_f1"]) for row in finals])
        rows.append({"method": f"{strategy}_no_dp", "accuracy_mean": acc_mean, "accuracy_std": acc_std,
                     "macro_f1_mean": f1_mean, "runs": runs})

    path = RESULTS_DIR / "baselines.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["data_source"])
        writer.writeheader()
        writer.writerows([{**row, "data_source": DATA_SOURCE} for row in rows])
    print(f"Saved baselines to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full FedAvg/FedProx x ε grid")
    parser.add_argument("--runs", type=int, default=3, help="repeats per setting (proposal: 3)")
    args = parser.parse_args()

    # check=True stops the sweep immediately if a run fails
    for strategy in STRATEGIES:
        for eps in EPSILONS:
            for run in range(1, args.runs + 1):
                subprocess.run(
                    [sys.executable, RUN_SCRIPT, str(eps), "--strategy", strategy, "--run", str(run)],
                    check=True,
                )
    summarise(args.runs)
    save_clinic_counts()

    # Reference points: no-DP federated runs and the centralised baseline
    for strategy in STRATEGIES:
        for run in range(1, args.runs + 1):
            subprocess.run(
                [sys.executable, RUN_SCRIPT, "--no-dp", "--strategy", strategy, "--run", str(run)],
                check=True,
            )
    subprocess.run([sys.executable, CENTRALIZED_SCRIPT, "--runs", str(args.runs)], check=True)
    summarise_baselines(args.runs)
