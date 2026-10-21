
"""Train an exploratory tongue-image Hb regression model.

Dataset: ImageHB sample (26 participants).
Validation selects the best checkpoint.
Held-out test participants are not evaluated here.
"""

import argparse
import json
import random
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image, ImageOps
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT.parent / "datasets"

DB_PATH = DATA_ROOT / "ayurai_image_catalog.sqlite3"

SPLIT_PATH = (
    DATA_ROOT / "splits" / "imagehb_tongue_hb_split.csv"
)

MODEL_PATH = (
    DATA_ROOT / "trained_model_artifacts"
    / "imagehb_tongue"
    / "efficientnet_b0_best.pth"
)

REPORT_DIR = (
    REPO_ROOT / "component1"
    / "evaluation" / "images" / "imagehb_tongue"
)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

SEED = 42


def set_seed():
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)


def load_records():
    """Load Hb-linked tongue images from the existing catalogue."""
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT participant_id, file_path, hb_g_dl
            FROM hb_image_records
            WHERE source = 'imagehb_sample'
              AND modality = 'tongue'
              AND hb_g_dl IS NOT NULL
            ORDER BY participant_id
            """,
            conn,
        )

    if df.empty:
        raise RuntimeError("No ImageHB tongue records found")

    df["participant_id"] = df["participant_id"].astype(str)
    df["hb_g_dl"] = pd.to_numeric(
        df["hb_g_dl"], errors="raise"
    )

    if df["participant_id"].duplicated().any():
        raise RuntimeError(
            "Multiple tongue images per participant found. "
            "Update the splitting logic before training."
        )

    if not np.isfinite(df["hb_g_dl"].to_numpy()).all():
        raise RuntimeError("Invalid Hb values found")

    missing = [
        path for path in df["file_path"]
        if not Path(path).is_file()
    ]

    if missing:
        raise FileNotFoundError(
            f"{len(missing)} tongue files missing. "
            f"First missing file: {missing[0]}"
        )

    print("Tongue images:", len(df))
    print("Participants:", df["participant_id"].nunique())

    return df


def get_splits(df):
    """Create once, then reuse participant-level split membership."""
    SPLIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ids = sorted(df["participant_id"].unique().tolist())

    if SPLIT_PATH.exists():
        split_df = pd.read_csv(
            SPLIT_PATH, dtype={"participant_id": str}
        )

        if (
            split_df["participant_id"].duplicated().any()
            or set(split_df["participant_id"]) != set(ids)
            or not set(split_df["split"]).issubset(
                {"train", "validation", "test"}
            )
        ):
            raise RuntimeError(
                "Saved participant split does not match dataset"
            )

        print("Reusing existing participant split")

    else:
        if len(ids) < 20:
            raise RuntimeError(
                "Not enough independent participants for this experiment"
            )

        trainval_ids, test_ids = train_test_split(
            ids, test_size=5, random_state=SEED
        )

        train_ids, val_ids = train_test_split(
            trainval_ids, test_size=5, random_state=SEED
        )

        split_lookup = {
            **{pid: "train" for pid in train_ids},
            **{pid: "validation" for pid in val_ids},
            **{pid: "test" for pid in test_ids},
        }

        split_df = pd.DataFrame({
            "participant_id": ids,
            "split": [split_lookup[pid] for pid in ids],
        })

        split_df.to_csv(SPLIT_PATH, index=False)
        print("Saved NEW participant-level split:", SPLIT_PATH)

    merged = df.merge(
        split_df, on="participant_id",
        how="left", validate="one_to_one"
    )

    if merged["split"].isna().any():
        raise RuntimeError("Some participants have no split")

    subsets = {
        name: merged[merged["split"] == name].copy()
        for name in ("train", "validation", "test")
    }

    for name, subset in subsets.items():
        if subset.empty:
            raise RuntimeError(f"Empty {name} split")
        print(f"{name}: {len(subset)} participants")

    return subsets


class TongueDataset(Dataset):
    """Load tongue photographs with consistent image preprocessing."""

    def __init__(self, records, mean_hb, std_hb, augment=False):
        self.records = records.reset_index(drop=True)
        self.mean_hb = mean_hb
        self.std_hb = std_hb

        operations = []

        if augment:
            operations.append(
                transforms.ColorJitter(
                    brightness=0.10,
                    contrast=0.10,
                    saturation=0.05,
                )
            )

        operations.extend([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        self.transform = transforms.Compose(operations)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        row = self.records.iloc[index]

        with Image.open(row["file_path"]) as image:
            rgba = image.convert("RGBA")

            background = Image.new(
                "RGBA", rgba.size, (255, 255, 255, 255)
            )
            background.alpha_composite(rgba)

            rgb = background.convert("RGB")

            rgb = ImageOps.pad(
                rgb,
                (224, 224),
                method=Image.Resampling.BILINEAR,
                color=(255, 255, 255),
            )

        image_tensor = self.transform(rgb)

        target = (
            (float(row["hb_g_dl"]) - self.mean_hb)
            / self.std_hb
        )

        return image_tensor, torch.tensor(
            target, dtype=torch.float32
        )


def make_model():
    """Freeze ImageNet backbone and train an Hb regression head."""
    model = efficientnet_b0(
        weights=EfficientNet_B0_Weights.DEFAULT
    )

    for parameter in model.features.parameters():
        parameter.requires_grad = False

    input_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(input_features, 1)

    return model.to(DEVICE)


def predict(model, loader, mean_hb, std_hb):
    """Return actual and estimated Hb in g/dL."""
    model.eval()

    actual = []
    predicted = []

    with torch.no_grad():
        for images, targets in loader:
            images = images.to(DEVICE)

            outputs = model(images).flatten()

            estimates = (
                outputs.cpu().numpy() * std_hb + mean_hb
            )
            ground_truth = (
                targets.numpy() * std_hb + mean_hb
            )

            actual.extend(ground_truth.tolist())
            predicted.extend(estimates.tolist())

    return np.asarray(actual), np.asarray(predicted)


def train(epochs):
    set_seed()

    print("AYURAI - IMAGEHB TONGUE Hb REGRESSION")
    print("Device:", DEVICE)

    records = load_records()
    subsets = get_splits(records)

    train_df = subsets["train"]
    val_df = subsets["validation"]

    # Calculate statistics from TRAIN participants only.
    mean_hb = float(train_df["hb_g_dl"].mean())
    std_hb = max(
        float(train_df["hb_g_dl"].std(ddof=0)), 0.1
    )

    train_loader = DataLoader(
        TongueDataset(
            train_df, mean_hb, std_hb, augment=True
        ),
        batch_size=8,
        shuffle=True,
        num_workers=0,
    )

    val_loader = DataLoader(
        TongueDataset(
            val_df, mean_hb, std_hb, augment=False
        ),
        batch_size=8,
        shuffle=False,
        num_workers=0,
    )

    naive_mae = mean_absolute_error(
        val_df["hb_g_dl"],
        np.full(len(val_df), mean_hb),
    )

    print(f"Baseline validation MAE: {naive_mae:.4f} g/dL")

    model = make_model()

    optimizer = torch.optim.Adam(
        model.classifier.parameters(), lr=0.0005
    )

    criterion = nn.SmoothL1Loss()

    best_mae = float("inf")
    best_rmse = float("inf")
    best_epoch = 0

    history = []

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(1, epochs + 1):
        model.train()

        # Keep frozen backbone batch normalization fixed.
        model.features.eval()

        total_loss = 0.0
        total_count = 0

        for images, targets in train_loader:
            images = images.to(DEVICE)
            targets = targets.to(DEVICE)

            optimizer.zero_grad()

            outputs = model(images).flatten()
            loss = criterion(outputs, targets)

            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(images)
            total_count += len(images)

        y_true, y_pred = predict(
            model, val_loader, mean_hb, std_hb
        )

        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(
            mean_squared_error(y_true, y_pred)
        )

        train_loss = total_loss / total_count

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_MAE_g_dl": mae,
            "val_RMSE_g_dl": rmse,
        })

        print(
            f"Epoch {epoch}/{epochs} | "
            f"loss {train_loss:.4f} | "
            f"val MAE {mae:.4f} | "
            f"RMSE {rmse:.4f}"
        )

        if mae < best_mae:
            best_mae = float(mae)
            best_rmse = float(rmse)
            best_epoch = epoch

            torch.save({
                "model_state_dict": model.state_dict(),
                "architecture": "efficientnet_b0",
                "task": "hb_regression",
                "source": "imagehb_sample",
                "modality": "tongue",
                "mean_hb": mean_hb,
                "std_hb": std_hb,
                "best_epoch": epoch,
                "selected_by": "validation_MAE",
            }, MODEL_PATH)

            print("  -> Best checkpoint saved")

    pd.DataFrame(history).to_csv(
        REPORT_DIR / "training_history.csv",
        index=False
    )

    comparison = pd.DataFrame([
        {
            "model": "Train_Mean_Hb_Baseline",
            "val_MAE_g_dl": naive_mae,
            "val_RMSE_g_dl": np.sqrt(
                mean_squared_error(
                    val_df["hb_g_dl"],
                    np.full(len(val_df), mean_hb),
                )
            ),
        },
        {
            "model": "EfficientNet_B0",
            "val_MAE_g_dl": best_mae,
            "val_RMSE_g_dl": best_rmse,
        },
    ])

    comparison.to_csv(
        REPORT_DIR / "validation_comparison.csv",
        index=False
    )

    protocol = {
        "dataset": "imagehb_sample",
        "modality": "tongue",
        "independent_participants": len(records),
        "train_participants": len(train_df),
        "validation_participants": len(val_df),
        "test_participants": len(subsets["test"]),
        "best_epoch": best_epoch,
        "best_validation_MAE_g_dl": best_mae,
        "baseline_validation_MAE_g_dl": naive_mae,
        "test_evaluated": False,
        "limitation": (
            "Only 26 participants; results are exploratory "
            "and highly sensitive to the split."
        ),
    }

    (REPORT_DIR / "protocol.json").write_text(
        json.dumps(protocol, indent=2),
        encoding="utf-8"
    )

    print("\nFINAL TONGUE VALIDATION")
    print(comparison.to_string(index=False))
    print("Best epoch:", best_epoch)
    print("Checkpoint:", MODEL_PATH)
    print("Reports:", REPORT_DIR)
    print("Held-out test participants: NOT evaluated")
    print("Experimental Hb estimation only.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--epochs", type=int, default=10
    )

    args = parser.parse_args()

    if args.epochs < 1:
        parser.error("--epochs must be at least 1")

    train(args.epochs)
