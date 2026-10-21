
"""Held-out evaluation of the selected four-wavelength PPG model.

Uses the original participant split and saved model.
Does not retrain or change hyperparameters.
"""

import json

import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error, mean_squared_error

import train_four_wavelength_hb as training


def metrics(name, actual, predicted):
    return {
        "model": name,
        "test_participants": len(actual),
        "test_MAE_g_dl": float(
            mean_absolute_error(actual, predicted)
        ),
        "test_RMSE_g_dl": float(
            np.sqrt(mean_squared_error(actual, predicted))
        ),
        "mean_error_g_dl": float(
            np.mean(predicted - actual)
        ),
    }


def main():
    print("AYURAI - FOUR-WAVELENGTH PPG HELD-OUT TEST")

    output = (
        training.REPORT_DIR
        / "four_wavelength_heldout_test.csv"
    )

    # Keep the reserved test set as a one-time evaluation.
    if output.exists():
        print("Held-out test already completed.")
        print(pd.read_csv(output).to_string(index=False))
        return

    if not training.MODEL_PATH.exists():
        raise FileNotFoundError(
            "Saved PPG model missing. Train the model first."
        )

    if not training.SPLIT_PATH.exists():
        raise FileNotFoundError(
            "Original participant split missing."
        )

    # Load our own previously trained model artifact.
    artifact = joblib.load(training.MODEL_PATH)

    if (
        artifact.get("source_dataset")
        != "Hb_PPG_FourWavelength"
        or artifact.get("task") != "hb_regression"
        or artifact.get("red_wavelength_nm") != 660
        or artifact.get("ir_wavelength_nm") != 940
    ):
        raise ValueError("Unexpected model artifact")

    df = training.split_dataset(
        training.load_dataset()
    )

    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]

    if len(test) != 51:
        raise RuntimeError(
            f"Unexpected test population: {len(test)}"
        )

    features = artifact["feature_names"]

    missing_features = [
        name for name in features
        if name not in test.columns
    ]

    if missing_features:
        raise RuntimeError(
            f"Missing test features: {missing_features}"
        )

    actual = test["hb_g_dl"].to_numpy(dtype=float)

    predicted = artifact["model"].predict(
        test[features]
    )

    if (
        len(predicted) != len(actual)
        or not np.isfinite(predicted).all()
    ):
        raise RuntimeError("Invalid model predictions")

    # Baseline must use the TRAINING participants only.
    train_mean_hb = float(
        train["hb_g_dl"].mean()
    )

    baseline_predictions = np.full(
        len(test),
        train_mean_hb,
        dtype=float,
    )

    results = pd.DataFrame([
        metrics(
            "Train_Mean_Hb_Baseline",
            actual,
            baseline_predictions,
        ),
        metrics(
            artifact["model_name"],
            actual,
            predicted,
        ),
    ])

    training.REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results.to_csv(output, index=False)

    protocol = {
        "dataset": "Hb_PPG_FourWavelength",
        "model": artifact["model_name"],
        "selected_by": artifact["selected_by"],
        "channels_nm": [660, 940],
        "train_participants": len(train),
        "test_participants": len(test),
        "test_evaluated": True,
        "model_retrained_on_test": False,
        "note": (
            "This evaluates the saved validation-selected "
            "model on previously held-out participants."
        ),
    }

    protocol_file = (
        training.REPORT_DIR
        / "four_wavelength_heldout_protocol.json"
    )

    protocol_file.write_text(
        json.dumps(protocol, indent=2),
        encoding="utf-8",
    )

    print("\nFINAL HELD-OUT TEST RESULTS")
    print(results.to_string(index=False))

    baseline_mae = results.iloc[0]["test_MAE_g_dl"]
    model_mae = results.iloc[1]["test_MAE_g_dl"]

    print(
        "\nModel beats test mean baseline:",
        bool(model_mae < baseline_mae),
    )

    print("Saved:", output)
    print("No retraining performed.")


if __name__ == "__main__":
    main()
