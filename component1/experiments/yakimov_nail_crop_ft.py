"""AyurAI C1 Experiment B (RESEARCH ONLY): Yakimov Hb regression from annotated nail crops.

Same model, starting weights and training settings as Experiment A; only the input changes
(three annotated nail crops per patient instead of the whole photograph). Every crop stays in its
patient's partition; predictions are averaged per patient and ALL metrics are patient-level.

The held-out TEST split is dropped as soon as the split file is read: no test image, box or Hb
value is used. This is not a production pathway (the live webcam has no validated nail detector).

Run from the repository root:
    python -m component1.experiments.yakimov_nail_crop_ft --preflight   # checks only
    python -m component1.experiments.yakimov_nail_crop_ft --train       # Experiment B (GPU)
    python -m component1.experiments.yakimov_nail_crop_ft --compare     # validation comparison of all models
"""

import argparse
import ast
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image, ImageOps
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch.utils.data import DataLoader, Dataset

from component1.experiments import yakimov_whole_frame_ft as exp_a
from component1.models.images import train_yakimov_hb_models as production
from component1.models.images.unified_image_inference import make_model

CONFIG_FILE = Path(__file__).with_name("yakimov_nail_crop_ft_v1.json")
DATA_ROOT = production.DATA_ROOT
IMAGE_SIZE = 224


def train_val_records():
    """Saved 175/37 train/validation split with nail boxes. Test rows are discarded immediately."""
    splits = exp_a.load_splits()  # validates the saved 175/37/38 split; never creates a new one
    records = splits[splits.split.isin(["train", "validation"])].copy()
    del splits
    meta = pd.read_csv(DATA_ROOT / "nailbeds" / "Yakimov_Hb_2024" / "metadata.csv", dtype={"PATIENT_ID": str})
    meta = meta[meta.PATIENT_ID.isin(set(records.participant_id))]  # train/validation patients only
    records = records.merge(meta[["PATIENT_ID", "HB_LEVEL_GperL", "NAIL_BOUNDING_BOXES"]],
                            left_on="participant_id", right_on="PATIENT_ID", how="left", validate="one_to_one")
    if records.NAIL_BOUNDING_BOXES.isna().any():
        raise ValueError("A train/validation patient has no nail annotation")
    if not np.allclose(records.hb_g_dl, records.HB_LEVEL_GperL / 10):
        raise ValueError("Split Hb (g/dL) and metadata Hb (g/L) disagree")
    records["boxes"] = records.NAIL_BOUNDING_BOXES.map(ast.literal_eval)
    if not records.boxes.map(len).eq(3).all():
        raise ValueError("Expected three annotated nails per patient")
    return records.drop(columns=["PATIENT_ID", "HB_LEVEL_GperL", "NAIL_BOUNDING_BOXES"]).reset_index(drop=True)


def square_crop(box, width, height, margin, jitter=None, rng=None):
    """Square around a [y1, x1, y2, x2] box, kept inside the photo (no padding, no stretching)."""
    y1, x1, y2, x2 = box
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"Box {box} outside {width}x{height} image")
    side = max(x2 - x1, y2 - y1) * (1 + 2 * margin)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if jitter is not None:
        side *= 1 + rng.uniform(-jitter["crop_scale_jitter"], jitter["crop_scale_jitter"])
        cx += rng.uniform(-1, 1) * jitter["crop_centre_jitter_fraction"] * side
        cy += rng.uniform(-1, 1) * jitter["crop_centre_jitter_fraction"] * side
    side = min(side, width, height)
    left = min(max(cx - side / 2, 0), width - side)
    top = min(max(cy - side / 2, 0), height - side)
    return left, top, left + side, top + side


class NailCropDataset(Dataset):
    """One item per annotated nail; the patient's Hb is the target and the patient index is kept."""

    def __init__(self, records, config, train):
        self.records = records.reset_index(drop=True)
        self.margin = config["crop"]["margin_each_side"]
        self.aug = config["augmentation"] if train else None
        self.rng = np.random.default_rng(config["seed"])
        self.images = {}
        for path in self.records.file_path:  # 175 + 37 photos (~300 MB) decoded once
            with Image.open(path) as original:
                self.images[path] = ImageOps.exif_transpose(original).convert("RGB")
        self.items = [(i, j) for i in range(len(self.records)) for j in range(3)]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        patient, nail = self.items[index]
        record = self.records.iloc[patient]
        image = self.images[record.file_path]
        box = square_crop(record.boxes[nail], *image.size, self.margin, self.aug, self.rng)
        crop = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR, box=box)
        if self.aug is not None and self.rng.random() < self.aug["horizontal_flip_p"]:
            crop = ImageOps.mirror(crop)
        return production.TRANSFORM(crop), torch.tensor(float(record.hb_g_dl), dtype=torch.float32), patient


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, float), np.asarray(predicted, float)
    return {
        "patients": int(len(actual)),
        "mae_g_dl": float(mean_absolute_error(actual, predicted)),
        "rmse_g_dl": float(math.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
        "mean_error_g_dl": float(np.mean(predicted - actual)),
    }


def patient_predictions(model, dataset, device, mean, std):
    """Average the three nail predictions (g/dL) of each patient."""
    model.eval()
    sums = np.zeros(len(dataset.records))
    counts = np.zeros(len(dataset.records))
    loader = DataLoader(dataset, batch_size=32, shuffle=False, num_workers=0)
    with torch.inference_mode():
        for images, _, patients in loader:
            hb = model(images.to(device)).squeeze(1).cpu().numpy() * std + mean
            np.add.at(sums, patients.numpy(), hb)
            np.add.at(counts, patients.numpy(), 1)
    if not (counts == 3).all():
        raise RuntimeError("Each patient must contribute exactly three crops")
    return sums / counts


def preflight(config):
    print("AYURAI EXPERIMENT B — PREFLIGHT (research only; no training, no test data)")
    exp_a.seed_everything(config["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device, torch.cuda.get_device_name(0) if device.type == "cuda" else "")
    records = train_val_records()
    counts = records.split.value_counts().to_dict()
    if counts != {"train": 175, "validation": 37}:
        raise ValueError(f"Unexpected train/validation counts {counts}")
    print(f"Patients with 3 usable nail boxes: train {counts['train']}, validation {counts['validation']} (test dropped)")
    sides = []
    for r in records.itertuples():
        for box in r.boxes:
            left, top, right, _ = square_crop(box, 800, 600, config["crop"]["margin_each_side"])
            sides.append(right - left)
    sides = np.array(sides)
    print(f"Crop side px: min {sides.min():.0f} / median {np.median(sides):.0f} / max {sides.max():.0f} "
          f"-> upscale to {IMAGE_SIZE}: median x{IMAGE_SIZE / np.median(sides):.1f}, max x{IMAGE_SIZE / sides.min():.1f}")

    train_rows = records[records.split == "train"]
    mean, std = float(train_rows.hb_g_dl.mean()), float(train_rows.hb_g_dl.std(ddof=0))
    model, saved, source, backbone, head = exp_a.build_model(config, device)
    if not (math.isclose(mean, saved["train_hb_mean"]) and math.isclose(std, saved["train_hb_std"])):
        raise ValueError("Train Hb statistics differ from the checkpoint normalisation")
    print(f"Checkpoint {source.name}: strict load OK; Hb scaling {mean:.4f} / {std:.4f} matches")

    start = time.perf_counter()
    train_set = NailCropDataset(train_rows, config, train=True)
    val_set = NailCropDataset(records[records.split == "validation"], config, train=False)
    print(f"Datasets: {len(train_set)} training crops from {len(train_rows)} patients, "
          f"{len(val_set)} validation crops; images decoded in {time.perf_counter() - start:.1f}s")
    image, hb, patient = train_set[0]
    print(f"Sample: tensor {tuple(image.shape)}, Hb {float(hb):.1f} g/dL, patient index {patient}")

    exp_a.set_train_mode(model, config["keep_batchnorm_running_stats_frozen"])
    loader = DataLoader(train_set, batch_size=config["batch_size"], shuffle=True, num_workers=0,
                        generator=torch.Generator().manual_seed(config["seed"]))
    start = time.perf_counter()
    for step, (images, hb, _) in enumerate(loader):  # forward/backward only: NO optimizer step, weights unchanged
        loss = nn.SmoothL1Loss()(model(images.to(device)).squeeze(1), ((hb - mean) / std).to(device))
        loss.backward()
        model.zero_grad(set_to_none=True)
        if step == 4:
            break
    if device.type == "cuda":
        torch.cuda.synchronize()
        per_step = (time.perf_counter() - start) / 5
        print(f"Measured {per_step:.2f}s per training step; peak GPU memory {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB")
        steps = math.ceil(len(train_set) / config["batch_size"])
        print(f"Estimated epoch ~{steps * per_step + 3:.0f}s -> {config['max_epochs']} epochs max ~{config['max_epochs'] * (steps * per_step + 3) / 60:.1f} min")
    epoch0 = metrics(val_set.records.hb_g_dl, patient_predictions(model, val_set, device, mean, std))
    print(f"Epoch-0 reference (production whole-frame weights applied to crops), patient-level validation MAE {epoch0['mae_g_dl']:.3f}")
    a_ckpt = DATA_ROOT / config["experiment_a_checkpoint"]
    print("Experiment A checkpoint present for comparison:", a_ckpt.is_file())
    root = DATA_ROOT / config["output_root"]
    root.mkdir(parents=True, exist_ok=True)
    print("Next run folder would be:", exp_a.new_run_dir(config))
    print("No test images, boxes or Hb labels were used.")


def train(config):
    exp_a.seed_everything(config["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("CUDA not available: refusing to run the full experiment on CPU")
    records = train_val_records()
    train_rows = records[records.split == "train"]
    mean, std = float(train_rows.hb_g_dl.mean()), float(train_rows.hb_g_dl.std(ddof=0))
    model, saved, source, backbone, head = exp_a.build_model(config, device)
    if not (math.isclose(mean, saved["train_hb_mean"]) and math.isclose(std, saved["train_hb_std"])):
        raise ValueError("Train Hb statistics differ from the checkpoint normalisation")
    train_set = NailCropDataset(train_rows, config, train=True)
    val_set = NailCropDataset(records[records.split == "validation"], config, train=False)
    loader = DataLoader(train_set, batch_size=config["batch_size"], shuffle=True, num_workers=0,
                        generator=torch.Generator().manual_seed(config["seed"]))

    run_dir = exp_a.new_run_dir(config)
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "config.json").write_text(json.dumps({
        **config,
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "device": torch.cuda.get_device_name(0), "torch_version": torch.__version__,
        "source_checkpoint_sha256": exp_a.sha256(source),
        "split_file_sha256": exp_a.sha256(production.SPLIT_FILE),
        "train_hb_mean": mean, "train_hb_std": std, "test_set_used": False,
    }, indent=2), encoding="utf-8")
    (run_dir / "split_participants.json").write_text(json.dumps({
        name: sorted(records.loc[records.split == name, "participant_id"].astype(str)) for name in ("train", "validation")
    } | {"test": "38 patients withheld; not read by this experiment"}, indent=2), encoding="utf-8")

    optimizer = torch.optim.AdamW(
        [{"params": backbone, "lr": config["lr_backbone"]}, {"params": head, "lr": config["lr_head"]}],
        weight_decay=config["weight_decay"],
    )
    criterion = nn.SmoothL1Loss()
    stop = config["early_stopping"]
    actual = val_set.records.hb_g_dl.to_numpy()
    first = metrics(actual, patient_predictions(model, val_set, device, mean, std))
    history = [{"epoch": 0, "train_loss": None, **first, "note": "production whole-frame weights on crops (reference only)"}]
    print(f"Epoch 0 (reference): patient val MAE {first['mae_g_dl']:.4f} | RMSE {first['rmse_g_dl']:.4f}")
    best, best_epoch, waited = math.inf, 0, 0
    candidate = run_dir / "candidate_efficientnet_b0_nailcrop.pth"
    started = time.perf_counter()

    for epoch in range(1, config["max_epochs"] + 1):
        exp_a.set_train_mode(model, config["keep_batchnorm_running_stats_frozen"])
        running, seen = 0.0, 0
        for images, hb, _ in loader:
            images, target = images.to(device), ((hb - mean) / std).to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images).squeeze(1), target)
            loss.backward()
            nn.utils.clip_grad_norm_(backbone + head, config["grad_clip_norm"])
            optimizer.step()
            running += loss.item() * len(images)
            seen += len(images)
        result = metrics(actual, patient_predictions(model, val_set, device, mean, std))
        history.append({"epoch": epoch, "train_loss": running / seen, **result, "note": ""})
        pd.DataFrame(history).to_csv(run_dir / "history.csv", index=False)
        print(f"Epoch {epoch}/{config['max_epochs']} | loss {running / seen:.4f} | patient val MAE {result['mae_g_dl']:.4f} "
              f"| RMSE {result['rmse_g_dl']:.4f} | R2 {result['r2']:.3f}")
        if result["mae_g_dl"] < best - stop["min_delta"]:
            best, best_epoch, waited = result["mae_g_dl"], epoch, 0
            torch.save({
                "architecture": config["architecture"], "model_state_dict": model.state_dict(),
                "train_hb_mean": mean, "train_hb_std": std, "best_epoch": epoch,
                "patient_validation_mae_g_dl": result["mae_g_dl"], "patient_validation_rmse_g_dl": result["rmse_g_dl"],
                "input": "annotated nail crop (research only)", "aggregation": config["patient_aggregation"],
                "source": "yakimov_hb_2024", "target_unit": "g/dL", "experiment": run_dir.name,
                "fine_tuned_from": config["source_checkpoint"], "deployment_status": config["deployment_status"],
            }, candidate)
        else:
            waited += 1
            if waited >= stop["patience"]:
                print(f"Early stopping: no patient-level validation MAE improvement for {stop['patience']} epochs")
                break

    summary = {
        "best_epoch": best_epoch, "best_patient_val_mae_g_dl": best,
        "production_whole_frame_val_mae_g_dl": saved["validation_mae_g_dl"],
        "beats_production_val_mae": best < saved["validation_mae_g_dl"],
        "training_seconds": round(time.perf_counter() - started, 1),
        "candidate_checkpoint": str(candidate), "test_set_used": False,
        "note": "Patient-level validation only (37 patients). Run --compare for the four-way validation comparison.",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    exp_a.plot([{"epoch": h["epoch"], "train_loss": h["train_loss"], "val_mae_g_dl": h["mae_g_dl"],
                 "val_rmse_g_dl": h["rmse_g_dl"]} for h in history], run_dir,
               float(np.mean(np.abs(actual - mean))))
    print(json.dumps(summary, indent=2))
    print("Outputs:", run_dir)


def latest_run(config):
    runs = sorted((DATA_ROOT / config["output_root"]).glob(f"{config['run_name_prefix']}*"),
                  key=lambda p: int(p.name.removeprefix(config["run_name_prefix"])))
    if not runs or not (runs[-1] / "candidate_efficientnet_b0_nailcrop.pth").is_file():
        raise FileNotFoundError("No completed Experiment B run with a candidate checkpoint")
    return runs[-1]


def compare(config):
    """Four-way comparison on the same 37 validation patients, all at patient level."""
    exp_a.seed_everything(config["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    records = train_val_records()
    train_rows, val_rows = records[records.split == "train"], records[records.split == "validation"]
    mean, std = float(train_rows.hb_g_dl.mean()), float(train_rows.hb_g_dl.std(ddof=0))
    actual = val_rows.hb_g_dl.to_numpy()
    run_dir = latest_run(config)

    def load(path):
        saved = torch.load(path, map_location="cpu", weights_only=True)
        model = make_model(config["architecture"], 1)
        model.load_state_dict(saved["model_state_dict"], strict=True)
        return model.to(device)

    whole_frame = DataLoader(production.HbImageDataset(val_rows), batch_size=32, shuffle=False, num_workers=0)

    def whole_frame_predictions(model):  # one photo per patient: already patient level
        model.eval()
        out = []
        with torch.inference_mode():
            for images, _ in whole_frame:
                out.extend((model(images.to(device)).squeeze(1).cpu().numpy() * std + mean).tolist())
        return np.array(out)

    predictions = {
        "train_mean_baseline": np.full(len(actual), mean),
        "original_whole_frame": whole_frame_predictions(load(exp_a.PRODUCTION_DIR / Path(config["source_checkpoint"]).name)),
        "experiment_a_whole_frame_ft": whole_frame_predictions(load(DATA_ROOT / config["experiment_a_checkpoint"])),
        "experiment_b_nail_crop_ft": patient_predictions(load(run_dir / "candidate_efficientnet_b0_nailcrop.pth"),
                                                         NailCropDataset(val_rows, config, train=False), device, mean, std),
    }
    rng = np.random.default_rng(config["seed"])
    boot = rng.integers(0, len(actual), size=(5000, len(actual)))
    base_error = np.abs(predictions["original_whole_frame"] - actual)
    rows = []
    for name, pred in predictions.items():
        error = np.abs(pred - actual)
        diff = (error[boot] - base_error[boot]).mean(axis=1)
        rows.append({"model": name, **metrics(actual, pred),
                     "mae_diff_vs_original_g_dl": float(error.mean() - base_error.mean()),
                     "mae_diff_95ci_low": float(np.percentile(diff, 2.5)),
                     "mae_diff_95ci_high": float(np.percentile(diff, 97.5))})
    table = pd.DataFrame(rows)
    table.to_csv(run_dir / "validation_comparison_patient_level.csv", index=False)
    pd.DataFrame({"participant_id": val_rows.participant_id.to_numpy(), "actual_hb_g_dl": actual,
                  **{f"pred_{k}": v for k, v in predictions.items()}}).to_csv(
        run_dir / "validation_patient_predictions.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].boxplot([np.abs(p - actual) for p in predictions.values()], tick_labels=[k.replace("_", "\n") for k in predictions])
    axes[0].set(title="Absolute error per validation patient (n=37)", ylabel="|predicted - lab Hb| (g/dL)")
    for name, pred in predictions.items():
        if name != "train_mean_baseline":
            axes[1].scatter(actual, pred, label=name, s=18, alpha=0.75)
    lims = [actual.min() - 0.5, actual.max() + 0.5]
    axes[1].plot(lims, lims, "k--", linewidth=1)
    axes[1].set(title="Predicted vs laboratory Hb (validation)", xlabel="Lab Hb (g/dL)", ylabel="Predicted Hb (g/dL)")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(run_dir / "validation_comparison.png", dpi=150)
    plt.close(fig)
    print(table.round(4).to_string(index=False))
    print("Validation only; candidates were selected on this same validation set, so their results are optimistic.")
    print("Outputs:", run_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--train", action="store_true")
    mode.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    {"preflight": preflight, "train": train, "compare": compare}[next(k for k, v in vars(args).items() if v)](config)


if __name__ == "__main__":
    main()
