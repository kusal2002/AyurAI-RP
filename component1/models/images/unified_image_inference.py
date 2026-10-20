"""AyurAI C1: run saved dataset-specific CNNs on ONE new image.

This is an inference smoke-test, not calibrated anaemia diagnosis or fusion.
Usage (from repo root):
  python component1/models/images/unified_image_inference.py --modality conjunctiva --image "path/to/eye.png"
  python component1/models/images/unified_image_inference.py --modality nails --image "path/to/nail.jpg"
"""

import argparse
import json
from pathlib import Path

import torch
from PIL import Image, ImageOps
from torchvision import transforms
from torchvision.models import efficientnet_b0, resnet50

REPO_ROOT = Path(__file__).resolve().parents[3]
WEIGHT_ROOT = REPO_ROOT.parent / "datasets" / "trained_model_artifacts"

# Same input photo is evaluated by BOTH dataset-specific models for that region.
CHECKPOINTS = {
    "conjunctiva": [
        ("cp_anemic_v2", "classification", "efficientnet_b0",
         WEIGHT_ROOT / "efficientnet_b0_best.pth"),
        ("ghana_conjunctiva", "classification", "resnet50",
         WEIGHT_ROOT / "ghana_conjunctiva" / "resnet_50_best.pth"),
    ],
    "nails": [
        ("ghana_fingernail", "classification", "resnet50",
         WEIGHT_ROOT / "ghana_fingernail" / "resnet_50_best.pth"),
        ("yakimov_hb_2024", "hb_regression", "efficientnet_b0",
         WEIGHT_ROOT / "yakimov_hb_2024" / "efficientnet_b0_best.pth"),
    ],
}

PREPROCESS = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])


def prepare_image(path):
    """Match the 224x224 white-background preprocessing used in training."""
    with Image.open(path) as original:
        rgba = ImageOps.exif_transpose(original).convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        rgb = ImageOps.pad(bg.convert("RGB"), (224, 224),
                           method=Image.Resampling.BILINEAR,
                           color=(255, 255, 255))
    return PREPROCESS(rgb).unsqueeze(0)


def make_model(architecture, output_count):
    """Recreate training architecture without downloading pretrained weights."""
    if architecture == "efficientnet_b0":
        model = efficientnet_b0(weights=None)
        model.classifier[-1] = torch.nn.Linear(
            model.classifier[-1].in_features, output_count)
    elif architecture == "resnet50":
        model = resnet50(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, output_count)
    else:
        raise ValueError(f"Unknown architecture: {architecture}")
    return model


def infer_image(image_path, modality, device=None):
    """Return separate outputs. Do NOT average class scores and Hb values."""
    if modality not in CHECKPOINTS:
        raise ValueError("modality must be conjunctiva or nails")
    image_path = Path(image_path).expanduser().resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Input photo does not exist: {image_path}")

    device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    image = prepare_image(image_path).to(device)
    results = []

    for source, task, architecture, checkpoint_path in CHECKPOINTS[modality]:
        if not checkpoint_path.is_file():
            results.append({"source": source, "status": "checkpoint_missing",
                            "expected_path": str(checkpoint_path)})
            continue

        saved = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        if task == "hb_regression":
            if (not isinstance(saved, dict)
                    or "model_state_dict" not in saved
                    or "train_hb_mean" not in saved
                    or "train_hb_std" not in saved):
                raise ValueError(f"Unexpected Hb checkpoint format: {checkpoint_path}")
            state = saved["model_state_dict"]
            mean = float(saved["train_hb_mean"])
            std = float(saved["train_hb_std"])
            if std <= 0:
                raise ValueError("Invalid Hb target scaling in checkpoint")
            output_count = 1
        else:
            state = saved
            output_count = 2

        model = make_model(architecture, output_count)
        model.load_state_dict(state, strict=True)
        model = model.to(device).eval()
        with torch.inference_mode():
            output = model(image)

        if task == "classification":
            # Uncalibrated class score; NOT a validated disease probability.
            score = float(torch.softmax(output[0], dim=0)[1].item())
            results.append({"source": source, "task": task,
                            "anaemia_class_score_uncalibrated": round(score, 4),
                            "predicted_class_at_0_5": int(score >= 0.5)})
        else:
            hb = float(output[0, 0].item()) * std + mean
            results.append({"source": source, "task": task,
                            "estimated_hb_g_dl_experimental": round(hb, 3)})
        del model

    return {"modality": modality, "device": str(device),
            "results": results,
            "note": "Separate experimental model outputs only; no calibrated fusion or diagnosis."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modality", choices=["conjunctiva", "nails"], required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None)
    args = parser.parse_args()
    print(json.dumps(infer_image(args.image, args.modality, args.device), indent=2))


if __name__ == "__main__":
    main()
