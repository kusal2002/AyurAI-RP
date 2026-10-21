
"""AyurAI: four-wavelength PPG Hb regression experiment.

Uses 660 nm RED and 940 nm IR channels.
Fits models using independent participant-level splits.
Selects by validation MAE; does not evaluate held-out test.
"""

import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from scipy.signal import butter, sosfiltfilt, welch
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT.parent / "datasets"

DATASET = (
    DATA_ROOT / "PPG"
    / "Hb_PPG_FourWavelength"
    / "Hb_PPG_Dataset"
)

CSV_DIR = DATASET / "data_csv"
METADATA = DATASET / "subject information.xlsx"

MODEL_DIR = DATA_ROOT / "trained_model_artifacts" / "ppg"
REPORT_DIR = REPO_ROOT / "component1" / "evaluation" / "ppg"

MODEL_PATH = MODEL_DIR / "four_wavelength_best.joblib"
SPLIT_PATH = DATA_ROOT / "splits" / "four_wavelength_ppg.csv"


def clean_signal(values):
    series = pd.to_numeric(
        pd.Series(values), errors="coerce"
    )

    series = series.interpolate(
        limit_direction="both"
    )

    arr = series.to_numpy(dtype=np.float64)

    if not np.isfinite(arr).all():
        raise ValueError("PPG contains unusable samples")

    if len(arr) < 200:
        raise ValueError("PPG recording is too short")

    return arr


def channel_features(samples, fs, name):
    """Extract RED/IR features using time-aware filtering."""
    samples = clean_signal(samples)

    dc = float(np.median(samples))
    scale = max(abs(dc), 1.0)

    relative = (samples - dc) / scale

    sos = butter(
        2, [0.6, 3.0],
        btype="bandpass",
        fs=fs,
        output="sos",
    )

    filtered = sosfiltfilt(sos, relative)

    frequencies, power = welch(
        filtered,
        fs=fs,
        nperseg=min(1024, len(filtered)),
    )

    band = (frequencies >= 0.6) & (frequencies <= 3.0)

    if not np.any(band):
        raise ValueError("Insufficient frequency resolution")

    selected_power = power[band]
    selected_freq = frequencies[band]

    peak_index = int(np.argmax(selected_power))

    features = {
        f"{name}_ac_dc": float(np.std(filtered)),
        f"{name}_p2p": float(
            np.percentile(filtered, 95)
            - np.percentile(filtered, 5)
        ),
        f"{name}_raw_variability": float(
            np.std(relative)
        ),
        f"{name}_pulse_bpm_candidate": float(
            selected_freq[peak_index] * 60.0
        ),
        f"{name}_pulse_power_ratio": float(
            selected_power.max()
            / (selected_power.sum() + 1e-12)
        ),
        f"{name}_gradient_variability": float(
            np.std(np.diff(filtered))
        ),
    }

    return features, filtered


def extract_features(red, ir, fs):
    """Reusable feature extractor for later live-device experiments."""
    if not np.isfinite(fs) or fs <= 6.5:
        raise ValueError("Invalid PPG sampling frequency")

    if len(red) != len(ir):
        raise ValueError("RED and IR lengths differ")

    red_features, red_filtered = channel_features(
        red, fs, "red"
    )
    ir_features, ir_filtered = channel_features(
        ir, fs, "ir"
    )

    if (
        np.std(red_filtered) > 1e-12
        and np.std(ir_filtered) > 1e-12
    ):
        correlation = float(
            np.corrcoef(
                red_filtered, ir_filtered
            )[0, 1]
        )
    else:
        correlation = 0.0

    ratio = (
        red_features["red_ac_dc"]
        / (ir_features["ir_ac_dc"] + 1e-12)
    )

    features = {
        **red_features,
        **ir_features,
        "red_ir_correlation": correlation,
        "red_ir_pulsatility_ratio": ratio,
    }

    if not all(
        np.isfinite(value)
        for value in features.values()
    ):
        raise ValueError("Non-finite extracted features")

    return features


def load_dataset():
    if not CSV_DIR.is_dir():
        raise FileNotFoundError(CSV_DIR)

    if not METADATA.is_file():
        raise FileNotFoundError(METADATA)

    metadata = pd.read_excel(METADATA)

    required = [
        "ID",
        "Hemoglobin (g/L)",
        "Signal length (second)",
    ]

    missing = [
        column for column in required
        if column not in metadata.columns
    ]

    if missing:
        raise ValueError(
            f"Missing metadata columns: {missing}"
        )

    metadata = metadata.copy()
    metadata["ID"] = pd.to_numeric(
        metadata["ID"], errors="coerce"
    )
    metadata = metadata.dropna(subset=["ID"])

    metadata["ID"] = metadata["ID"].astype(int)

    if metadata["ID"].duplicated().any():
        raise ValueError("Duplicate participant IDs")

    records_by_id = metadata.set_index("ID")
    rows = []
    seen = set()

    files = sorted(CSV_DIR.glob("*.csv"))

    print("Signal CSV files:", len(files))

    for file in files:
        numbers = re.findall(r"\d+", file.stem)

        if len(numbers) != 1:
            raise ValueError(
                f"Cannot identify participant from {file.name}"
            )

        participant_id = int(numbers[0])

        if participant_id in seen:
            raise ValueError(
                f"Duplicate PPG participant: {participant_id}"
            )

        seen.add(participant_id)

        if participant_id not in records_by_id.index:
            raise ValueError(
                f"Participant {participant_id} missing in metadata"
            )

        subject = records_by_id.loc[participant_id]

        hb_g_l = float(subject["Hemoglobin (g/L)"])
        duration = float(subject["Signal length (second)"])

        if (
            not np.isfinite(hb_g_l)
            or not np.isfinite(duration)
            or duration <= 0
        ):
            raise ValueError(
                f"Invalid Hb/duration for participant {participant_id}"
            )

        signal = pd.read_csv(
            file, usecols=["660nm", "940nm"]
        )

        fs = len(signal) / duration

        features = extract_features(
            signal["660nm"].to_numpy(),
            signal["940nm"].to_numpy(),
            fs,
        )

        rows.append({
            "participant_id": participant_id,
            "hb_g_dl": hb_g_l / 10.0,
            "sampling_rate_hz": fs,
            **features,
        })

    df = pd.DataFrame(rows).sort_values(
        "participant_id"
    ).reset_index(drop=True)

    if len(df) < 200:
        raise RuntimeError(
            f"Expected approximately 252 participants; found {len(df)}"
        )

    if (
        (df["hb_g_dl"] < 4).any()
        or (df["hb_g_dl"] > 25).any()
    ):
        raise ValueError(
            "Hb conversion or metadata appears incorrect"
        )

    print("Participants:", len(df))
    print(
        "Hb range:",
        round(df["hb_g_dl"].min(), 2),
        "to",
        round(df["hb_g_dl"].max(), 2),
        "g/dL",
    )

    return df


def split_dataset(df):
    """Create an independent participant split and reuse it."""
    SPLIT_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )

    ids = df["participant_id"].tolist()

    if SPLIT_PATH.exists():
        splits = pd.read_csv(SPLIT_PATH)

        if (
            splits["participant_id"].duplicated().any()
            or set(splits["participant_id"]) != set(ids)
            or set(splits["split"]) != {
                "train", "validation", "test"
            }
        ):
            raise ValueError(
                "Saved split is incompatible with data"
            )

        print("Reusing saved participant split")

    else:
        trainval, test = train_test_split(
            ids, test_size=0.20, random_state=42
        )

        train, validation = train_test_split(
            trainval, test_size=0.20, random_state=42
        )

        membership = {
            **{sid: "train" for sid in train},
            **{sid: "validation" for sid in validation},
            **{sid: "test" for sid in test},
        }

        splits = pd.DataFrame({
            "participant_id": ids,
            "split": [membership[sid] for sid in ids],
        })

        splits.to_csv(SPLIT_PATH, index=False)
        print("New participant split saved")

    merged = df.merge(
        splits, on="participant_id",
        validate="one_to_one",
    )

    for name in ("train", "validation", "test"):
        print(
            f"{name}:",
            (merged["split"] == name).sum(),
        )

    return merged


def train_models():
    print("AYURAI - FOUR-WAVELENGTH PPG Hb TRAINING")

    df = split_dataset(load_dataset())

    feature_names = [
        column for column in df.columns
        if column not in {
            "participant_id", "hb_g_dl",
            "sampling_rate_hz", "split"
        }
    ]

    train = df[df["split"] == "train"]
    val = df[df["split"] == "validation"]

    X_train = train[feature_names]
    y_train = train["hb_g_dl"]

    X_val = val[feature_names]
    y_val = val["hb_g_dl"]

    models = {
        "Mean_Baseline": DummyRegressor(
            strategy="mean"
        ),
        "Ridge": make_pipeline(
            StandardScaler(),
            Ridge(alpha=10.0),
        ),
        "RandomForest": RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        ),
        "GradientBoosting": HistGradientBoostingRegressor(
            max_iter=100,
            max_leaf_nodes=10,
            l2_regularization=1.0,
            random_state=42,
        ),
    }

    results = []
    trained = {}

    for name, model in models.items():
        model.fit(X_train, y_train)

        predictions = model.predict(X_val)

        mae = mean_absolute_error(
            y_val, predictions
        )

        rmse = np.sqrt(
            mean_squared_error(y_val, predictions)
        )

        results.append({
            "model": name,
            "val_MAE_g_dl": float(mae),
            "val_RMSE_g_dl": float(rmse),
        })

        trained[name] = model

        print(
            f"{name:<18} "
            f"MAE={mae:.4f} "
            f"RMSE={rmse:.4f}"
        )

    results_df = pd.DataFrame(results)

    learned_results = results_df[
        results_df["model"] != "Mean_Baseline"
    ]

    winner = learned_results.sort_values(
        "val_MAE_g_dl"
    ).iloc[0]["model"]

    baseline_mae = results_df.loc[
        results_df["model"] == "Mean_Baseline",
        "val_MAE_g_dl",
    ].iloc[0]

    winner_mae = results_df.loc[
        results_df["model"] == winner,
        "val_MAE_g_dl",
    ].iloc[0]

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump({
        "model": trained[winner],
        "model_name": winner,
        "feature_names": feature_names,
        "red_wavelength_nm": 660,
        "ir_wavelength_nm": 940,
        "task": "hb_regression",
        "target_unit": "g/dL",
        "source_dataset": "Hb_PPG_FourWavelength",
        "selected_by": "validation_MAE",
    }, MODEL_PATH)

    results_df.to_csv(
        REPORT_DIR / "four_wavelength_validation.csv",
        index=False,
    )

    (REPORT_DIR / "four_wavelength_protocol.json").write_text(
        json.dumps({
            "participants": len(df),
            "train_participants": len(train),
            "validation_participants": len(val),
            "test_participants": int(
                (df["split"] == "test").sum()
            ),
            "selected_model": winner,
            "best_validation_MAE_g_dl": float(winner_mae),
            "baseline_validation_MAE_g_dl": float(baseline_mae),
            "test_evaluated": False,
            "wavelengths_nm": [660, 940],
        }, indent=2),
        encoding="utf-8",
    )

    print("\nFINAL MODEL COMPARISON")
    print(results_df.to_string(index=False))
    print("\nSelected trained model:", winner)
    print("Beats mean baseline:", winner_mae < baseline_mae)
    print("Checkpoint:", MODEL_PATH)
    print("Held-out test: NOT EVALUATED")


if __name__ == "__main__":
    train_models()
