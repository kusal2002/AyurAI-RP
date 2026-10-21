"""AyurAI C1 Experiment A: conservative whole-frame fine-tuning of the Yakimov nail-bed Hb model.

Starts from the production checkpoint, unfreezes only the last EfficientNet-B0 blocks,
and selects the best epoch by VALIDATION MAE. The held-out TEST split is never loaded:
its participant IDs are only recorded so the final locked comparison can be audited.

Production files are read-only here. Outputs go to a NEW versioned folder under
../datasets/trained_model_artifacts/experiments/yakimov_hb_2024/ (never overwritten).

Run from the repository root:
    python -m component1.experiments.yakimov_whole_frame_ft --preflight   # checks only, no training
    python -m component1.experiments.yakimov_whole_frame_ft --train       # the experiment
"""

import argparse
import hashlib
import json
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.transforms import v2

from component1.models.images import train_yakimov_hb_models as production
from component1.models.images.unified_image_inference import make_model

CONFIG_FILE = Path(__file__).with_name("yakimov_whole_frame_ft_v1.json")
DATA_ROOT = production.DATA_ROOT
ARTIFACTS = DATA_ROOT / "trained_model_artifacts"
PRODUCTION_DIR = ARTIFACTS / "yakimov_hb_2024"
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


class AugmentedHbDataset(production.HbImageDataset):
    """Production preprocessing, then small geometric augmentation only (no colour changes)."""

    def __init__(self, records, aug):
        super().__init__(records)
        white = [(1.0 - m) / s for m, s in zip(IMAGENET_MEAN, IMAGENET_STD)]  # padding colour after normalisation
        self.augment = v2.Compose([
            v2.RandomHorizontalFlip(p=aug["horizontal_flip_p"]),
            v2.RandomAffine(degrees=aug["rotation_degrees"],
                            translate=(aug["translate_fraction"], aug["translate_fraction"]),
                            scale=tuple(aug["scale_range"]), fill=white),
        ])

    def __getitem__(self, index):
        image, hb = super().__getitem__(index)
        return self.augment(image), hb


def load_splits():
    """Reuse the saved participant split; refuse to run if it would have to be (re)created."""
    if not production.SPLIT_FILE.is_file():
        raise FileNotFoundError(f"Saved split missing; refusing to create a new one: {production.SPLIT_FILE}")
    splits = production.load_or_create_splits()  # validates the saved split against the catalogue; no writes
    counts = splits.split.value_counts().to_dict()
    if counts != {"train": 175, "validation": 37, "test": 38}:
        raise ValueError(f"Unexpected split sizes {counts}; expected 175/37/38")
    if splits.groupby("participant_id").split.nunique().max() != 1 or splits.participant_id.duplicated().any():
        raise ValueError("A participant appears in more than one partition")
    test_files = set(splits.loc[splits.split == "test", "file_path"])
    if test_files & set(splits.loc[splits.split != "test", "file_path"]):
        raise ValueError("A test image is also listed in train/validation")
    return splits


def build_model(config, device):
    """Production architecture + production weights; unfreeze only the configured late blocks."""
    source = PRODUCTION_DIR / Path(config["source_checkpoint"]).name
    saved = torch.load(source, map_location="cpu", weights_only=True)
    if saved.get("architecture") != config["architecture"]:
        raise ValueError("Source checkpoint architecture mismatch")
    model = make_model(config["architecture"], 1)
    model.load_state_dict(saved["model_state_dict"], strict=True)
    for parameter in model.parameters():
        parameter.requires_grad = False
    backbone = []
    for index in config["unfreeze_feature_blocks"]:
        for parameter in model.features[index].parameters():
            parameter.requires_grad = True
            backbone.append(parameter)
    head = list(model.classifier.parameters())
    for parameter in head:
        parameter.requires_grad = True
    return model.to(device), saved, source, backbone, head


def set_train_mode(model, freeze_bn_stats):
    model.train()
    if freeze_bn_stats:  # small batches: keep ImageNet/production BatchNorm running statistics fixed
        for module in model.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()


def new_run_dir(config):
    root = DATA_ROOT / config["output_root"]
    version = 1
    while (root / f"{config['run_name_prefix']}{version}").exists():
        version += 1
    run_dir = root / f"{config['run_name_prefix']}{version}"
    if PRODUCTION_DIR.resolve() in run_dir.resolve().parents or run_dir.resolve() == PRODUCTION_DIR.resolve():
        raise RuntimeError("Refusing to write inside the production model directory")
    return run_dir


def loaders(splits, config, mean, std):
    train_rows = splits[splits.split == "train"]
    val_rows = splits[splits.split == "validation"]
    train_loader = DataLoader(
        AugmentedHbDataset(train_rows, config["augmentation"]), batch_size=config["batch_size"], shuffle=True,
        num_workers=0, generator=torch.Generator().manual_seed(config["seed"]),
    )
    val_loader = DataLoader(production.HbImageDataset(val_rows), batch_size=config["batch_size"], shuffle=False, num_workers=0)
    return train_loader, val_loader


def preflight(config):
    print("AYURAI EXPERIMENT A — PREFLIGHT (no training, no test evaluation)")
    seed_everything(config["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device, torch.cuda.get_device_name(0) if device.type == "cuda" else "")

    splits = load_splits()
    train = splits[splits.split == "train"]
    print("Split OK: 175/37/38, each participant in exactly one partition, no shared files")

    model, saved, source, backbone, head = build_model(config, device)
    mean, std = float(train.hb_g_dl.mean()), float(train.hb_g_dl.std(ddof=0))
    if not (math.isclose(mean, saved["train_hb_mean"], rel_tol=1e-9) and math.isclose(std, saved["train_hb_std"], rel_tol=1e-9)):
        raise ValueError("Train-split Hb statistics differ from the checkpoint's stored normalisation")
    print(f"Checkpoint {source.name}: strict load OK; Hb scaling mean {mean:.4f} / std {std:.4f} matches checkpoint")
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Trainable parameters: {trainable:,} of {total:,} (features {config['unfreeze_feature_blocks']} + classifier)")

    train_loader, val_loader = loaders(splits, config, mean, std)
    image, hb = train_loader.dataset[0]
    plain, _ = production.HbImageDataset(train.iloc[:1])[0]
    print(f"Train sample: augmented {tuple(image.shape)} | production {tuple(plain.shape)} | Hb {float(hb):.1f} g/dL")

    val_mae, val_rmse = production.validation_metrics(model, val_loader, device, mean, std)
    print(f"Production checkpoint re-evaluated on VALIDATION: MAE {val_mae:.4f} (recorded {saved['validation_mae_g_dl']:.4f}) | RMSE {val_rmse:.4f}")
    if abs(val_mae - saved["validation_mae_g_dl"]) > 1e-3:
        raise ValueError("Could not reproduce the recorded validation MAE: preprocessing or weights differ")

    # One forward/backward pass to check memory and gradient routing. No optimizer step: weights stay unchanged.
    set_train_mode(model, config["keep_batchnorm_running_stats_frozen"])
    images, hb = next(iter(train_loader))
    start = time.perf_counter()
    loss = nn.SmoothL1Loss()(model(images.to(device)).squeeze(1), ((hb - mean) / std).to(device))
    loss.backward()
    if device.type == "cuda":
        torch.cuda.synchronize()
    step = time.perf_counter() - start
    frozen_with_grad = [n for n, p in model.named_parameters() if not p.requires_grad and p.grad is not None]
    if frozen_with_grad:
        raise RuntimeError(f"Frozen parameters received gradients: {frozen_with_grad[:3]}")
    if device.type == "cuda":
        print(f"One training step: {step:.2f}s, peak GPU memory {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB")

    root = DATA_ROOT / config["output_root"]
    root.mkdir(parents=True, exist_ok=True)
    probe = root / ".write_probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    print("Output root writable:", root)
    print("Next run folder would be:", new_run_dir(config))
    print("Held-out test images were NOT loaded.")


def train(config):
    seed_everything(config["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("CUDA not available: refusing to run the full experiment on CPU")
    splits = load_splits()
    train_rows = splits[splits.split == "train"]
    mean, std = float(train_rows.hb_g_dl.mean()), float(train_rows.hb_g_dl.std(ddof=0))
    model, saved, source, backbone, head = build_model(config, device)
    if not (math.isclose(mean, saved["train_hb_mean"]) and math.isclose(std, saved["train_hb_std"])):
        raise ValueError("Train-split Hb statistics differ from the checkpoint normalisation")
    train_loader, val_loader = loaders(splits, config, mean, std)

    run_dir = new_run_dir(config)
    run_dir.mkdir(parents=True, exist_ok=False)
    split_ids = {name: sorted(splits.loc[splits.split == name, "participant_id"].astype(str).tolist())
                 for name in ("train", "validation", "test")}
    (run_dir / "config.json").write_text(json.dumps({
        **config,
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "device": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "source_checkpoint_sha256": sha256(source),
        "train_hb_mean": mean, "train_hb_std": std,
        "split_file": str(production.SPLIT_FILE), "split_file_sha256": sha256(production.SPLIT_FILE),
        "test_set_used": False,
    }, indent=2), encoding="utf-8")
    (run_dir / "split_participants.json").write_text(json.dumps(split_ids, indent=2), encoding="utf-8")

    optimizer = torch.optim.AdamW(
        [{"params": backbone, "lr": config["lr_backbone"]}, {"params": head, "lr": config["lr_head"]}],
        weight_decay=config["weight_decay"],
    )
    criterion = nn.SmoothL1Loss()
    stop = config["early_stopping"]
    base_mae, base_rmse = production.validation_metrics(model, val_loader, device, mean, std)
    history = [{"epoch": 0, "train_loss": None, "val_mae_g_dl": base_mae, "val_rmse_g_dl": base_rmse, "note": "production checkpoint"}]
    print(f"Epoch 0 (production checkpoint): val MAE {base_mae:.4f} | RMSE {base_rmse:.4f}")
    best_mae, best_epoch, waited = base_mae, 0, 0
    candidate = run_dir / "candidate_efficientnet_b0.pth"

    for epoch in range(1, config["max_epochs"] + 1):
        set_train_mode(model, config["keep_batchnorm_running_stats_frozen"])
        running, seen = 0.0, 0
        for images, hb in train_loader:
            images, target = images.to(device), ((hb - mean) / std).to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images).squeeze(1), target)
            loss.backward()
            nn.utils.clip_grad_norm_(backbone + head, config["grad_clip_norm"])
            optimizer.step()
            running += loss.item() * len(images)
            seen += len(images)
        val_mae, val_rmse = production.validation_metrics(model, val_loader, device, mean, std)
        history.append({"epoch": epoch, "train_loss": running / seen, "val_mae_g_dl": val_mae, "val_rmse_g_dl": val_rmse, "note": ""})
        pd.DataFrame(history).to_csv(run_dir / "history.csv", index=False)
        print(f"Epoch {epoch}/{config['max_epochs']} | loss {running / seen:.4f} | val MAE {val_mae:.4f} | RMSE {val_rmse:.4f}")
        if val_mae < best_mae - stop["min_delta"]:
            best_mae, best_epoch, waited = val_mae, epoch, 0
            torch.save({  # Same keys as production so the existing inference code could load it later.
                "architecture": config["architecture"], "model_state_dict": model.state_dict(),
                "train_hb_mean": mean, "train_hb_std": std, "best_epoch": epoch,
                "validation_mae_g_dl": val_mae, "validation_rmse_g_dl": val_rmse,
                "source": "yakimov_hb_2024", "target_unit": "g/dL",
                "experiment": run_dir.name, "fine_tuned_from": config["source_checkpoint"],
            }, candidate)
        else:
            waited += 1
            if waited >= stop["patience"]:
                print(f"Early stopping: no validation MAE improvement for {stop['patience']} epochs")
                break

    baseline_mae = float((splits.loc[splits.split == "validation", "hb_g_dl"] - mean).abs().mean())
    summary = {
        "best_epoch": best_epoch,
        "best_val_mae_g_dl": best_mae,
        "production_val_mae_g_dl": base_mae,
        "train_mean_baseline_val_mae_g_dl": baseline_mae,
        "candidate_saved": best_epoch > 0,
        "candidate_checkpoint": str(candidate) if best_epoch > 0 else None,
        "test_set_used": False,
        "note": "Validation only. The 38-patient test set is reserved for one locked comparison.",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    plot(history, run_dir, baseline_mae)
    print(json.dumps(summary, indent=2))
    print("Outputs:", run_dir)


def plot(history, run_dir, baseline_mae):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.DataFrame(history)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    trained = df[df.epoch > 0]
    axes[0].plot(trained.epoch, trained.train_loss, marker="o")
    axes[0].set(title="Training loss (SmoothL1, normalised Hb)", xlabel="Epoch", ylabel="Loss")
    axes[1].plot(df.epoch, df.val_mae_g_dl, marker="o", label="Validation MAE")
    axes[1].plot(df.epoch, df.val_rmse_g_dl, marker="s", label="Validation RMSE")
    axes[1].axhline(baseline_mae, linestyle="--", color="grey", label="Train-mean baseline MAE")
    axes[1].set(title="Validation error (g/dL); epoch 0 = production model", xlabel="Epoch", ylabel="g/dL")
    axes[1].legend()
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(run_dir / "training_curves.png", dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="lightweight checks only")
    mode.add_argument("--train", action="store_true", help="run Experiment A (GPU)")
    args = parser.parse_args()
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if args.preflight:
        preflight(config)
    else:
        train(config)


if __name__ == "__main__":
    main()
