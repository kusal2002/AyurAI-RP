r"""AyurAI C1: preliminary participant-split fingernail Hb regression baselines.
Trains on Yakimov images indexed in local SQLite;  
Targets are laboratory Hb in g/dL."""

import argparse
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image, ImageOps
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import (
    EfficientNet_B0_Weights,
    MobileNet_V2_Weights,
    ResNet50_Weights,
    efficientnet_b0,
    mobilenet_v2,
    resnet50,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT.parent / "datasets"
DB_PATH = DATA_ROOT / "ayurai_image_catalog.sqlite3"
SPLIT_FILE = DATA_ROOT / "splits" / "yakimov_hb_regression_split.csv"
REPORT_DIR = REPO_ROOT / "component1" / "evaluation" / "images" / "yakimov_hb_2024"
WEIGHTS_DIR = DATA_ROOT / "trained_model_artifacts" / "yakimov_hb_2024"

TRANSFORM = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class HbImageDataset(Dataset):
    """Read one participant's nail photograph and measured Hb from a split."""

    def __init__(self, records):
        self.records = records.reset_index(drop=True)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        record = self.records.iloc[index]
        with Image.open(record.file_path) as original:
            rgba = ImageOps.exif_transpose(original).convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            background.alpha_composite(rgba)
            image = ImageOps.pad(
                background.convert("RGB"), (224, 224),
                method=Image.Resampling.BILINEAR, color=(255, 255, 255)
            )
        return TRANSFORM(image), torch.tensor(float(record.hb_g_dl), dtype=torch.float32)


def load_or_create_splits():
    """Generate participant-independent splits once, then always reuse them."""
    if not DB_PATH.is_file():
        raise FileNotFoundError(DB_PATH)

    with sqlite3.connect(DB_PATH) as conn:
        records = pd.read_sql_query(
            """SELECT participant_id, file_path, hb_g_dl
               FROM hb_image_records
               WHERE source = 'yakimov_hb_2024' AND modality = 'nails'
               ORDER BY participant_id""", conn
        )

    if len(records) < 30 or records.participant_id.isna().any():
        raise ValueError("Insufficient Yakimov records or missing participant IDs")
    if records.participant_id.duplicated().any():
        raise ValueError("More than one nail image per participant: review grouping")
    if not np.isfinite(records.hb_g_dl.to_numpy(dtype=float)).all():
        raise ValueError("Missing/invalid Hb values")
    missing = [p for p in records.file_path if not Path(p).is_file()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} image paths missing, first: {missing[0]}")

    if SPLIT_FILE.exists():
        saved = pd.read_csv(SPLIT_FILE, dtype={"participant_id": str})
        required = {"participant_id", "file_path", "hb_g_dl", "split"}
        if not required.issubset(saved.columns):
            raise ValueError("Existing Yakimov split file has missing columns")
        check = saved.merge(records, on="participant_id", how="outer", suffixes=("_old", "_new"), indicator=True)
        if (len(check) != len(records) or (check._merge != "both").any()
                or (check.file_path_old != check.file_path_new).any()
                or not np.allclose(check.hb_g_dl_old, check.hb_g_dl_new)
                or saved.participant_id.duplicated().any()):
            raise ValueError("Dataset changed since the original split; do not overwrite the saved splits")
        if set(saved["split"]) != {"train", "validation", "test"}:
            raise ValueError("Unrecognized or missing split assignment")
        result = saved
        print("Reusing saved patient-level splits:", SPLIT_FILE)
    else:
        ids = records.participant_id.tolist()
        training_ids, remaining_ids = train_test_split(ids, test_size=0.30, random_state=42)
        validation_ids, test_ids = train_test_split(remaining_ids, test_size=0.50, random_state=42)
        assignments = ({pid: "train" for pid in training_ids}
                       | {pid: "validation" for pid in validation_ids}
                       | {pid: "test" for pid in test_ids})
        result = records.copy()
        result["split"] = result.participant_id.map(assignments)
        SPLIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(SPLIT_FILE, index=False)
        print("Saved NEW participant-level splits:", SPLIT_FILE)

    assert result.groupby("participant_id")["split"].nunique().max() == 1
    for name in ("train", "validation", "test"):
        subset = result[result.split == name]
        print(f"  {name}: {len(subset)} images / {subset.participant_id.nunique()} participants")
    return result


def make_model(name):
    """Freeze ImageNet feature extractor and replace classification head with Hb regression."""
    if name == "mobilenetv2":
        model = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
        for parameter in model.parameters():
            parameter.requires_grad = False
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 1)
        head = model.classifier
    elif name == "efficientnet_b0":
        model = efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)
        for parameter in model.parameters():
            parameter.requires_grad = False
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 1)
        head = model.classifier
    elif name == "resnet50":
        model = resnet50(weights=ResNet50_Weights.DEFAULT)
        for parameter in model.parameters():
            parameter.requires_grad = False
        model.fc = nn.Linear(model.fc.in_features, 1)
        head = model.fc
    else:
        raise ValueError(f"Unknown architecture: {name}")
    return model, head


def validation_metrics(model, loader, device, target_mean, target_std):
    model.eval()
    actual, predicted = [], []
    with torch.inference_mode():
        for images, hb in loader:
            norm_prediction = model(images.to(device)).squeeze(1)
            pred_hb = norm_prediction * target_std + target_mean
            actual.extend(hb.numpy().tolist())
            predicted.extend(pred_hb.cpu().numpy().tolist())
    return (mean_absolute_error(actual, predicted),
            math.sqrt(mean_squared_error(actual, predicted)))


def train_one(name, splits, epochs, batch_size, device):
    torch.manual_seed(42)
    train_rows = splits[splits.split == "train"]
    val_rows = splits[splits.split == "validation"]
    target_mean = float(train_rows.hb_g_dl.mean())
    target_std = float(train_rows.hb_g_dl.std(ddof=0))
    if target_std < 1e-6:
        raise ValueError("Training Hb values lack variation")

    train_loader = DataLoader(
        HbImageDataset(train_rows), batch_size=batch_size, shuffle=True,
        num_workers=0, pin_memory=(device.type == "cuda"),
        generator=torch.Generator().manual_seed(42)
    )
    val_loader = DataLoader(
        HbImageDataset(val_rows), batch_size=batch_size, shuffle=False,
        num_workers=0, pin_memory=(device.type == "cuda")
    )

    model, head = make_model(name)
    model = model.to(device)
    optimizer = torch.optim.Adam(head.parameters(), lr=0.001)
    criterion = nn.SmoothL1Loss()
    checkpoint = WEIGHTS_DIR / f"{name}_best.pth"
    history = []
    best_mae = float("inf")
    best_epoch, best_rmse = None, None

    print(f"\n{name.upper()}: {epochs} epochs (frozen backbone)")
    for epoch in range(1, epochs + 1):
        model.eval()  # frozen backbone BatchNorm statistics must not update
        head.train()
        running_loss = 0.0
        for images, hb in train_loader:
            images, hb = images.to(device), hb.to(device)
            target = (hb - target_mean) / target_std
            optimizer.zero_grad()
            prediction = model(images).squeeze(1)
            loss = criterion(prediction, target)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * len(images)
        val_mae, val_rmse = validation_metrics(
            model, val_loader, device, target_mean, target_std
        )
        train_loss = running_loss / len(train_loader.dataset)
        history.append({"Model": name, "Epoch": epoch, "Train_Loss": train_loss,
                        "Val_MAE_g_dl": val_mae, "Val_RMSE_g_dl": val_rmse})
        print(f"Epoch {epoch}/{epochs} | loss {train_loss:.4f} | "
              f"val MAE {val_mae:.3f} g/dL | RMSE {val_rmse:.3f} g/dL")
        if val_mae < best_mae:
            best_mae, best_rmse, best_epoch = val_mae, val_rmse, epoch
            torch.save({
                "architecture": name, "model_state_dict": model.state_dict(),
                "train_hb_mean": target_mean, "train_hb_std": target_std,
                "best_epoch": best_epoch, "validation_mae_g_dl": best_mae,
                "source": "yakimov_hb_2024", "target_unit": "g/dL",
            }, checkpoint)

    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return ({"Model": name, "Best_Epoch": best_epoch,
             "Val_MAE_g_dl": best_mae, "Val_RMSE_g_dl": best_rmse}, history)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--model", choices=["all", "mobilenetv2", "efficientnet_b0", "resnet50"], default="all")
    args = parser.parse_args()
    if args.epochs <= 0 or args.batch_size <= 0:
        parser.error("--epochs and --batch-size must be positive")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("AYURAI - YAKIMOV NAIL Hb REGRESSION (g/dL)")
    print("Device:", device)
    if device.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))
    split_records = load_or_create_splits()
    training_mean = split_records.loc[split_records.split == "train", "hb_g_dl"].mean()
    validation_hb = split_records.loc[split_records.split == "validation", "hb_g_dl"]
    naive_mae = mean_absolute_error(validation_hb, [training_mean] * len(validation_hb))
    print(f"Baseline (predict train mean Hb) validation MAE: {naive_mae:.3f} g/dL")

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    models = (["mobilenetv2", "efficientnet_b0", "resnet50"]
              if args.model == "all" else [args.model])
    results, histories = [], []
    for name in models:
        result, history = train_one(name, split_records, args.epochs, args.batch_size, device)
        result["Naive_Val_MAE_g_dl"] = naive_mae
        results.append(result)
        histories.extend(history)
        pd.DataFrame(results).sort_values("Val_MAE_g_dl").to_csv(
            REPORT_DIR / "validation_comparison.csv", index=False)
        pd.DataFrame(histories).to_csv(REPORT_DIR / "training_history.csv", index=False)

    print("\nFINAL VALIDATION COMPARISON (lower MAE is better)")
    print(pd.DataFrame(results).sort_values("Val_MAE_g_dl").to_string(index=False))
    print("Held-out test images were NOT evaluated.")
    print("Research baseline only; no clinical screening claims.")
    print("Reports:", REPORT_DIR)


if __name__ == "__main__":
    main()
