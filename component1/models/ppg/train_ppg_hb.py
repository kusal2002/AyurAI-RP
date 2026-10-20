"""AyurAI C1 | Subject-independent baseline Hb regression from MAX30102 RED/IR.

Uses only raw PPG amplitudes from the public dataset (no age/sex, no lab values as features).
No sampling timestamps are available: these are amplitude/shape statistics, NOT heart-rate features.
Training/validation/test splitting is by subject_id and the held-out test is never evaluated here.
For research only; not a clinically validated Hb estimate.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT.parent / "datasets"
SOURCE = "hb_ppg_max30102"


def ppg_features(red, ir):
    """Return sampling-rate-independent time-domain RED/IR features for one person.

    Must be reused UNCHANGED for live recordings before inference. Device and recording
    protocol differences may still prevent transfer to the ESP32 live recordings.
    """
    red = np.asarray(red, dtype=np.float64)
    ir = np.asarray(ir, dtype=np.float64)
    if red.ndim != 1 or ir.ndim != 1 or len(red) != len(ir) or len(red) < 50:
        raise ValueError("Expected matching RED and IR waveforms with at least 50 samples")
    if not np.isfinite(red).all() or not np.isfinite(ir).all():
        raise ValueError("PPG waveform contains NaN or infinity")
    med_red, med_ir = float(np.median(red)), float(np.median(ir))
    if med_red <= 0 or med_ir <= 0:
        raise ValueError("Invalid non-positive PPG sensor baseline")
    rn, inn = red / med_red - 1.0, ir / med_ir - 1.0
    sr, si = float(np.std(rn)), float(np.std(inn))
    if sr < 1e-7 or si < 1e-7:
        raise ValueError("Flat PPG recording; cannot extract valid features")
    return {
        "red_dc": med_red,
        "ir_dc": med_ir,
        "red_ac_dc": sr,
        "ir_ac_dc": si,
        "red_rel_range": float(np.percentile(rn, 95) - np.percentile(rn, 5)),
        "ir_rel_range": float(np.percentile(inn, 95) - np.percentile(inn, 5)),
        "red_ir_dc_ratio": med_red / med_ir,
        "red_ir_ac_dc_ratio": sr / si,
        "red_ir_correlation": float(np.corrcoef(rn, inn)[0, 1]),
        "red_diff_variability": float(np.std(np.diff(rn))),
        "ir_diff_variability": float(np.std(np.diff(inn))),
    }


def load_features(db):
    if not db.is_file():
        raise FileNotFoundError(db)
    with sqlite3.connect(db) as conn:
        subjects = pd.read_sql_query(
            "SELECT subject_id, hb_g_dl FROM ppg_subjects WHERE source = ? ORDER BY subject_id",
            conn, params=(SOURCE,)
        )
        samples = pd.read_sql_query(
            """SELECT subject_id, sample_index, red_signal, ir_signal
               FROM ppg_signal_samples WHERE source = ? AND variant = 'raw'
               ORDER BY subject_id, sample_index""", conn, params=(SOURCE,)
        )
    if subjects.empty or samples.empty:
        raise ValueError("PPG tables are empty; run import_ppg_research.py first")
    if subjects.subject_id.duplicated().any() or subjects.hb_g_dl.isna().any():
        raise ValueError("Invalid or repeated participant labels")
    if samples.duplicated(["subject_id", "sample_index"]).any():
        raise ValueError("Duplicate recording sample index")
    if set(samples.subject_id) != set(subjects.subject_id):
        raise ValueError("Signal subjects do not match labelled subjects")
    features = []
    for sid, frame in samples.groupby("subject_id", sort=True):
        f = ppg_features(frame.red_signal.to_numpy(), frame.ir_signal.to_numpy())
        f["subject_id"] = int(sid)
        features.append(f)
    df = subjects.merge(pd.DataFrame(features), on="subject_id", validate="one_to_one")
    if not np.isfinite(df.drop(columns=["subject_id"]).to_numpy(dtype=float)).all():
        raise ValueError("Non-finite extracted features")
    return df


def get_splits(ids, split_file):
    ids = np.asarray(sorted(int(i) for i in ids))
    if split_file.exists():
        splits = pd.read_csv(split_file)
        if not {"subject_id", "split"}.issubset(splits.columns):
            raise ValueError("Existing split has unexpected columns")
        if (splits.subject_id.duplicated().any()
                or set(splits.subject_id) != set(ids)
                or set(splits.split) != {"train", "validation", "test"}):
            raise ValueError("Existing split is inconsistent; do not regenerate silently")
        print("Reusing existing participant split:", split_file)
    else:
        remaining, test = train_test_split(ids, test_size=0.20, random_state=42)
        train, val = train_test_split(remaining, test_size=0.20, random_state=42)
        splits = pd.DataFrame(
            [(int(s), name) for name, group in
             (("train", train), ("validation", val), ("test", test)) for s in group],
            columns=["subject_id", "split"]
        ).sort_values("subject_id")
        split_file.parent.mkdir(parents=True, exist_ok=True)
        splits.to_csv(split_file, index=False)
        print("Saved NEW participant split:", split_file)
    print("Subjects per split:", splits.split.value_counts().to_dict())
    return splits


def train(db, split_file, report_dir, artifact_dir):
    df = load_features(db)
    splits = get_splits(df.subject_id, split_file)
    df = df.merge(splits, on="subject_id", validate="one_to_one")
    features = [c for c in df if c not in ("subject_id", "hb_g_dl", "split")]
    tr, va = df[df.split == "train"], df[df.split == "validation"]
    X_tr, y_tr = tr[features].to_numpy(), tr.hb_g_dl.to_numpy()
    X_val, y_val = va[features].to_numpy(), va.hb_g_dl.to_numpy()

    candidates = {
        "Mean_Hb_Baseline": DummyRegressor(strategy="mean"),
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
        "RandomForest": RandomForestRegressor(
            n_estimators=150, max_depth=4, min_samples_leaf=3,
            random_state=42, n_jobs=-1
        ),
    }
    results = []
    models = {}
    for name, estimator in candidates.items():
        estimator.fit(X_tr, y_tr)
        predicted = estimator.predict(X_val)
        row = {
            "model": name, "train_subjects": len(tr), "val_subjects": len(va),
            "val_MAE_g_dl": mean_absolute_error(y_val, predicted),
            "val_RMSE_g_dl": float(np.sqrt(mean_squared_error(y_val, predicted))),
        }
        results.append(row)
        models[name] = estimator
    report = pd.DataFrame(results).sort_values("val_MAE_g_dl")
    best = report.iloc[0]
    report_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report.to_csv(report_dir / "validation_model_comparison.csv", index=False)
    (report_dir / "protocol.json").write_text(json.dumps({
        "source": SOURCE, "target": "Hb in g/dL", "selected_by": "validation MAE",
        "validation_winner": str(best["model"]),
        "features": features, "test_used": False,
        "limitation": "68 participants; PPG sampling rate unknown; transfer to live ESP32 unverified"
    }, indent=2), encoding="utf-8")
    joblib.dump({
        "model": models[str(best["model"])], "model_name": str(best["model"]),
        "features": features, "source": SOURCE, "training_subjects": len(tr),
        "validation_subjects": len(va)
    }, artifact_dir / "ppg_best_validation_model.joblib")
    print("\nAYURAI PPG Hb VALIDATION (g/dL; lower is better)")
    print(report.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("Validation winner:", best["model"])
    if best["model"] == "Mean_Hb_Baseline":
        print("WARNING: Signal models did NOT beat the mean-Hb baseline on validation.")
    print("Held-out test subjects NOT evaluated; test split preserved.")
    print("Model artifact:", artifact_dir / "ppg_best_validation_model.joblib")
    print("Report:", report_dir / "validation_model_comparison.csv")
    print("RESEARCH ONLY: no valid clinical screening or live-sensor claim.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "ayurai_image_catalog.sqlite3")
    ap.add_argument("--splits", type=Path, default=DATA_ROOT / "splits" / "ppg_hb_subject_split.csv")
    ap.add_argument("--reports", type=Path, default=ROOT / "component1" / "evaluation" / "ppg")
    ap.add_argument("--artifacts", type=Path, default=DATA_ROOT / "trained_model_artifacts" / "ppg")
    args = ap.parse_args()
    train(args.db, args.splits, args.reports, args.artifacts)


if __name__ == "__main__":
    main()
