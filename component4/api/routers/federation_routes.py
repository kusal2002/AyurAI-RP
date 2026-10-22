"""Serve the federated-learning experiment results written by federated/server.py."""

import csv
import re
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from models import User
from security import get_current_user
from settings import COMPONENT_DIR, RESULTS_DIR

# Reuse the experiment settings from federated/config.py (single source of truth)
sys.path.append(str(COMPONENT_DIR / "federated"))
import config as fl_config  # noqa: E402

router = APIRouter(prefix="/api/v1/c4/federation", tags=["Federated learning"])

# e.g. fedprox_eps0.5_run2.csv -> ("fedprox", "0.5", "2")
RUN_FILE = re.compile(r"^(fedavg|fedprox)_eps([0-9.]+)_run(\d+)\.csv$")
# Real per-clinic tier counts saved by federated/sweep.py (committed; no patient data)
CLINIC_COUNTS_FILE = RESULTS_DIR / "clinic_counts.csv"


def read_csv(path: Path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def to_float(value):
    return float(value) if value not in ("", None) else None


def clinic_tier_counts():
    """(Low, Moderate, High) patients per clinic, and whether they are real:
    1. the real features file, if it exists (same rule as federated/data.py);
    2. else results/clinic_counts.csv, the real counts saved by sweep.py (a server
       without the dataset, e.g. the deployed dashboard, still shows the real split);
    3. else the placeholder counts."""
    features_file = fl_config.FEATURES_FILE
    if features_file is not None and features_file.exists():
        counts = {clinic_id: [0, 0, 0] for clinic_id in fl_config.CLINIC_PROFILES}
        for row in read_csv(features_file):
            counts[int(row["clinic_id"])][int(row["tier"])] += 1
        return counts, True
    if CLINIC_COUNTS_FILE.exists():
        counts = {int(row["clinic_id"]): [int(row["low"]), int(row["moderate"]), int(row["high"])]
                  for row in read_csv(CLINIC_COUNTS_FILE)}
        return counts, True
    return {cid: list(p["label_counts"]) for cid, p in fl_config.CLINIC_PROFILES.items()}, False


@router.get("/config")
def experiment_config(user: User = Depends(get_current_user)):
    counts, real_data = clinic_tier_counts()
    return {
        "num_clinics": fl_config.NUM_CLINICS,
        "num_rounds": fl_config.NUM_ROUNDS,
        "local_epochs": fl_config.LOCAL_EPOCHS,
        "learning_rate": fl_config.LEARNING_RATE,
        "proximal_mu": fl_config.PROXIMAL_MU,
        "delta": fl_config.DELTA,
        "max_grad_norm": fl_config.MAX_GRAD_NORM,
        "epsilons": fl_config.EPSILONS,
        "real_data": real_data,
        "hb_thresholds": {"high_risk_below": fl_config.HB_HIGH_RISK_BELOW,
                          "low_risk_from": fl_config.HB_LOW_RISK_FROM},
        "clinics": [
            {
                "clinic_id": clinic_id,
                "name": profile["name"],
                "low": counts[clinic_id][0],
                "moderate": counts[clinic_id][1],
                "high": counts[clinic_id][2],
            }
            for clinic_id, profile in fl_config.CLINIC_PROFILES.items()
        ],
    }


@router.get("/runs")
def list_runs(user: User = Depends(get_current_user)):
    runs = []
    for path in sorted(RESULTS_DIR.glob("*.csv")):
        match = RUN_FILE.match(path.name)
        if not match:
            continue  # skip summary.csv and older files with other names
        strategy, eps, run = match.groups()
        runs.append({
            "strategy": strategy,
            "epsilon": float(eps),
            "run": int(run),
            "rounds": [
                {
                    "round": int(row["round"]),
                    "loss": to_float(row["loss"]),
                    "accuracy": to_float(row["accuracy"]),
                    "macro_f1": to_float(row.get("macro_f1")),
                    "epsilon_spent": to_float(row.get("epsilon_spent")),
                }
                for row in read_csv(path)
            ],
        })
    return runs


@router.get("/summary")
def summary(user: User = Depends(get_current_user)):
    path = RESULTS_DIR / "summary.csv"
    if not path.exists():
        raise HTTPException(404, "No summary yet — run federated/sweep.py first")
    return read_csv(path)


@router.get("/baselines")
def baselines(user: User = Depends(get_current_user)):
    """Reference points: majority class, centralised (no DP) and federated without DP."""
    path = RESULTS_DIR / "baselines.csv"
    if not path.exists():
        raise HTTPException(404, "No baselines yet — run federated/sweep.py first")
    return read_csv(path)
