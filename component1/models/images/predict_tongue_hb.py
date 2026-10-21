
"""Run the trained ImageHB tongue model on a new image."""

import argparse
import json
from pathlib import Path

import torch
from PIL import Image, ImageOps
from torch import nn
from torchvision import transforms
from torchvision.models import efficientnet_b0

DATA_ROOT = Path(__file__).resolve().parents[3].parent / "datasets"

MODEL_PATH = (
    DATA_ROOT / "trained_model_artifacts"
    / "imagehb_tongue" / "efficientnet_b0_best.pth"
)


def predict(image_path, *, verbose=True):
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    checkpoint = torch.load(
        MODEL_PATH, map_location="cpu", weights_only=True
    )

    if checkpoint.get("modality") != "tongue":
        raise ValueError("Incorrect model checkpoint")

    model = efficientnet_b0(weights=None)

    features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(features, 1)

    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device).eval()

    with Image.open(image_path) as image:
        rgba = image.convert("RGBA")

        background = Image.new(
            "RGBA", rgba.size, (255, 255, 255, 255)
        )
        background.alpha_composite(rgba)

        rgb = ImageOps.pad(
            background.convert("RGB"),
            (224, 224),
            method=Image.Resampling.BILINEAR,
            color=(255, 255, 255),
        )

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    tensor = transform(rgb).unsqueeze(0).to(device)

    with torch.inference_mode():
        normalized_hb = model(tensor).item()

    estimated_hb = (
        normalized_hb * checkpoint["std_hb"]
        + checkpoint["mean_hb"]
    )

    result = {
        "modality": "tongue",
        "source": "imagehb_sample",
        "model": "efficientnet_b0",
        "task": "hb_regression",
        "estimated_hb_g_dl_experimental": round(
            float(estimated_hb), 3
        ),
        "clinical_risk_category": None,
        "note": "Exploratory Hb estimate from a small dataset.",
    }

    if verbose:
        print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()

    predict(args.image)
