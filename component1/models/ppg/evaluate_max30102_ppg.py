"""AyurAI C1: one-time held-out MAX30102 Hb regression evaluation.

Place beside train_ppg_hb.py in component1/models/ppg/ and run from
repository root with the Component 1 virtual environment.

Outputs aggregate publication/demo graphics to component1/evaluation/ppg/.
Per-subject test predictions stay outside Git in ../datasets/.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from train_ppg_hb import DATA_ROOT, ROOT, SOURCE, get_splits, load_features

SPLIT_PATH = DATA_ROOT / "splits" / "ppg_hb_subject_split.csv"
MODEL_PATH = DATA_ROOT / "trained_model_artifacts" / "ppg" / "ppg_best_validation_model.joblib"
REPORT_DIR = ROOT / "component1" / "evaluation" / "ppg"
FIG_DIR = REPORT_DIR / "figures" / "max30102_hb"
PRIVATE_DIR = DATA_ROOT / "evaluation_artifacts" / "ppg"
SUMMARY_PATH = REPORT_DIR / "max30102_heldout_test_metrics.csv"


def score_regression(name: str, actual: np.ndarray, pred: np.ndarray) -> dict:
    return {
        "model": name,
        "test_participants": int(len(actual)),
        "test_MAE_g_dl": float(mean_absolute_error(actual, pred)),
        "test_RMSE_g_dl": float(np.sqrt(mean_squared_error(actual, pred))),
        "test_R2": float(r2_score(actual, pred)),
        "test_mean_error_g_dl": float(np.mean(pred - actual)),
    }


def render_plots(y: np.ndarray, pred: np.ndarray, baseline: np.ndarray, names: list[str]):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    errors = pred - y

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(y, pred, alpha=0.85, label=names[1])
    lo = float(min(y.min(), pred.min(), baseline.min()))
    hi = float(max(y.max(), pred.max(), baseline.max()))
    ax.plot([lo, hi], [lo, hi], linestyle="--", label="Ideal estimate")
    ax.set(xlabel="Laboratory Hb (g/dL)", ylabel="Model-estimated Hb (g/dL)",
           title=f"MAX30102 held-out Hb predictions (n={len(y)})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "actual_vs_predicted.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(pred, errors, alpha=0.85)
    ax.axhline(0, linestyle="--")
    ax.set(xlabel="Model-estimated Hb (g/dL)", ylabel="Prediction − laboratory Hb (g/dL)",
           title="Held-out residuals")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "residuals.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(np.abs(errors), bins=min(9, max(3, len(y) // 2)), edgecolor="black")
    ax.set(xlabel="Absolute Hb prediction error (g/dL)", ylabel="Participants",
           title="Held-out absolute error distribution")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "absolute_error_distribution.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    values = [float(mean_absolute_error(y, baseline)), float(mean_absolute_error(y, pred))]
    ax.bar(names, values)
    ax.set(ylabel="Held-out MAE (g/dL)", title="Model versus training-mean baseline")
    for idx, value in enumerate(values):
        ax.text(idx, value, f"{value:.3f}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "test_mae_comparison.png", dpi=180)
    plt.close(fig)


def main():
    print("AYURAI — MAX30102 HEMOGLOBIN HELD-OUT EVALUATION")
    if SUMMARY_PATH.exists():
        print("Existing held-out results found; not rerunning test evaluation:")
        print(pd.read_csv(SUMMARY_PATH).to_string(index=False))
        print("Graphs:", FIG_DIR)
        return

    if not SPLIT_PATH.is_file() or not MODEL_PATH.is_file():
        raise FileNotFoundError("Saved subject split or trained MAX30102 model is missing")

    # Only load your own trained artifact; joblib files from strangers are unsafe.
    artifact = joblib.load(MODEL_PATH)
    if artifact.get("source") != SOURCE:
        raise ValueError("Wrong PPG training dataset in model artifact")
    model = artifact.get("model")
    features = list(artifact.get("features", []))
    if model is None or not features:
        raise ValueError("Saved model or feature list is missing")

    db = DATA_ROOT / "ayurai_image_catalog.sqlite3"
    data = load_features(db)
    # get_splits reuses the ORIGINAL split; it must not recreate the test group.
    split_data = get_splits(data["subject_id"], SPLIT_PATH)
    data = data.merge(split_data, on="subject_id", validate="one_to_one")
    train = data.loc[data["split"] == "train"]
    test = data.loc[data["split"] == "test"]
    if len(test) != 14:
        raise RuntimeError(f"Expected 14 original held-out participants, got {len(test)}")
    if train.empty or test.empty:
        raise RuntimeError("Empty training or test split")
    if any(col not in data.columns for col in features):
        raise ValueError("Model feature schema does not match dataset")
    if set(train["subject_id"]) & set(test["subject_id"]):
        raise RuntimeError("Train/test subject leakage detected")

    y = test["hb_g_dl"].to_numpy(dtype=float)
    # Train script fits numpy arrays, so inference must also use numpy arrays.
    estimates = np.asarray(model.predict(test[features].to_numpy(dtype=float)), dtype=float)
    baseline = np.full(len(test), float(train["hb_g_dl"].mean()), dtype=float)
    if not np.isfinite(estimates).all():
        raise RuntimeError("Non-finite PPG model predictions")

    names = ["Training mean Hb", str(artifact.get("model_name", "Saved PPG model"))]
    results = pd.DataFrame([
        score_regression(names[0], y, baseline),
        score_regression(names[1], y, estimates),
    ])

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    # Keep participant-level predictions away from Git.
    pd.DataFrame({
        "subject_id": test["subject_id"].to_numpy(),
        "actual_hb_g_dl": y,
        "estimated_hb_g_dl": estimates,
        "baseline_estimated_hb_g_dl": baseline,
    }).to_csv(PRIVATE_DIR / "max30102_heldout_test_predictions.csv", index=False)

    render_plots(y, estimates, baseline, names)
    results.to_csv(SUMMARY_PATH, index=False)
    (REPORT_DIR / "max30102_heldout_test_protocol.json").write_text(
        json.dumps({
            "source": SOURCE,
            "model": names[1],
            "selected_prior_to_test_by": "validation MAE",
            "train_participants": int(len(train)),
            "test_participants": int(len(test)),
            "same_11_features_as_training": True,
            "test_retraining": False,
            "metrics": ["MAE", "RMSE", "R2", "mean_error"],
            "confusion_matrix_note": "Hb regression is not a classification task; no F1 or confusion matrix without an independently specified classification target.",
            "live_hardware_transfer_evaluated": False,
        }, indent=2), encoding="utf-8"
    )

    print("\nMAX30102 HELD-OUT TEST COMPARISON")
    print(results.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nModel beats baseline by test MAE:", bool(results.iloc[1]["test_MAE_g_dl"] < results.iloc[0]["test_MAE_g_dl"]))
    print("Graph folder:", FIG_DIR)
    print("Aggregate metrics:", SUMMARY_PATH)
    print("Participant predictions (outside Git):", PRIVATE_DIR)


if __name__ == "__main__":
    main()
