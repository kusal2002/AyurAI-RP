
"""Held-out test of the ImageHB tongue Hb regression model."""

import json

import numpy as np
import pandas as pd
import torch

from torch import nn
from torch.utils.data import DataLoader
from torchvision.models import efficientnet_b0
from sklearn.metrics import mean_absolute_error, mean_squared_error

import train_tongue_hb as training


def main():
    report_dir = training.REPORT_DIR
    output_path = report_dir / "heldout_test_metrics.csv"

    # Protect against accidentally repeating test evaluation.
    if output_path.exists():
        print("Test already evaluated. Existing results:")
        print(pd.read_csv(output_path).to_string(index=False))
        return

    if not training.SPLIT_PATH.exists():
        raise FileNotFoundError("Saved participant split missing")

    checkpoint = torch.load(
        training.MODEL_PATH,
        map_location="cpu",
        weights_only=True,
    )

    if (
        checkpoint["source"] != "imagehb_sample"
        or checkpoint["modality"] != "tongue"
    ):
        raise ValueError("Incorrect model checkpoint")

    records = training.load_records()
    splits = training.get_splits(records)

    train_df = splits["train"]
    test_df = splits["test"]

    mean_hb = float(checkpoint["mean_hb"])
    std_hb = float(checkpoint["std_hb"])

    if not np.isclose(
        mean_hb,
        train_df["hb_g_dl"].mean(),
        atol=1e-5,
    ):
        raise ValueError("Checkpoint and training split do not match")

    # Rebuild model without downloading pretrained weights.
    model = efficientnet_b0(weights=None)

    input_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(input_features, 1)

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model = model.to(training.DEVICE)
    model.eval()

    test_loader = DataLoader(
        training.TongueDataset(
            test_df,
            mean_hb,
            std_hb,
            augment=False,
        ),
        batch_size=8,
        shuffle=False,
        num_workers=0,
    )

    actual, predicted = training.predict(
        model,
        test_loader,
        mean_hb,
        std_hb,
    )

    baseline_predictions = np.full_like(
        actual, mean_hb
    )

    def calculate_metrics(name, estimates):
        return {
            "model": name,
            "test_participants": len(test_df),
            "test_MAE_g_dl": mean_absolute_error(
                actual, estimates
            ),
            "test_RMSE_g_dl": np.sqrt(
                mean_squared_error(actual, estimates)
            ),
        }

    results = pd.DataFrame([
        calculate_metrics(
            "Train_Mean_Hb_Baseline",
            baseline_predictions,
        ),
        calculate_metrics(
            "EfficientNet_B0",
            predicted,
        ),
    ])

    report_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)

    (report_dir / "heldout_test_protocol.json").write_text(
        json.dumps({
            "source": "imagehb_sample",
            "modality": "tongue",
            "selected_checkpoint_epoch": checkpoint["best_epoch"],
            "selected_by": "validation MAE",
            "test_participants": len(test_df),
            "test_evaluated": True,
            "note": "Exploratory evaluation using five participants."
        }, indent=2),
        encoding="utf-8",
    )

    print("\nAYURAI - TONGUE HELD-OUT TEST")
    print("Device:", training.DEVICE)
    print(results.to_string(index=False))
    print("Reports:", report_dir)
    print("No clinical risk classification inferred.")


if __name__ == "__main__":
    main()
