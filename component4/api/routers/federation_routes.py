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


def read_csv(path: Path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def to_float(value):
    return float(value) if value not in ("", None) else None


@router.get("/config")
def experiment_config(user: User = Depends(get_current_user)):
    return {
        "num_clinics": fl_config.NUM_CLINICS,
        "num_rounds": fl_config.NUM_ROUNDS,
        "local_epochs": fl_config.LOCAL_EPOCHS,
        "proximal_mu": fl_config.PROXIMAL_MU,
        "delta": fl_config.DELTA,
        "max_grad_norm": fl_config.MAX_GRAD_NORM,
        "epsilons": fl_config.EPSILONS,
        "clinics": [
            {
                "clinic_id": clinic_id,
                "name": profile["name"],
                "low": profile["label_counts"][0],
                "moderate": profile["label_counts"][1],
                "high": profile["label_counts"][2],
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
