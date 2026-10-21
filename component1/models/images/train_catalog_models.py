
# AyurAI Component 1 - Reusable CNN Model Comparison

import argparse
import time
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    recall_score
)

from torchvision.models import (
    mobilenet_v2,
    MobileNet_V2_Weights,
    efficientnet_b0,
    EfficientNet_B0_Weights,
    resnet50,
    ResNet50_Weights
)

from make_split_loaders import create_loaders
from catalog_dataset import REPO_ROOT


def build_model(name):
    """Load pretrained CNN and replace its classifier."""

    if name == "MobileNetV2":
        model = mobilenet_v2(
            weights=MobileNet_V2_Weights.DEFAULT
        )

        for p in model.parameters():
            p.requires_grad = False

        model.classifier[-1] = nn.Linear(
            model.classifier[-1].in_features, 2
        )

        head = model.classifier

    elif name == "EfficientNet-B0":
        model = efficientnet_b0(
            weights=EfficientNet_B0_Weights.DEFAULT
        )

        for p in model.parameters():
            p.requires_grad = False

        model.classifier[-1] = nn.Linear(
            model.classifier[-1].in_features, 2
        )

        head = model.classifier

    elif name == "ResNet-50":
        model = resnet50(
            weights=ResNet50_Weights.DEFAULT
        )

        for p in model.parameters():
            p.requires_grad = False

        model.fc = nn.Linear(
            model.fc.in_features, 2
        )

        head = model.fc

    else:
        raise ValueError(f"Unknown model: {name}")

    return model, head


def evaluate(model, loader, device):
    """Evaluate using validation data, not test data."""

    model.eval()

    actual = []
    predicted = []

    with torch.inference_mode():
        for images, labels in loader:
            images = images.to(device)

            outputs = model(images)
            predictions = outputs.argmax(dim=1)

            actual.extend(labels.tolist())
            predicted.extend(predictions.cpu().tolist())

    return {
        "Accuracy": accuracy_score(actual, predicted),
        "Balanced_Accuracy": balanced_accuracy_score(actual, predicted),
        "F1": f1_score(actual, predicted, zero_division=0),
        "Sensitivity": recall_score(
            actual, predicted, pos_label=1, zero_division=0
        ),
        "Specificity": recall_score(
            actual, predicted, pos_label=0, zero_division=0
        ),
    }


def train_model(name, loaders, source, epochs, device):
    """Train a classifier and save its best validation checkpoint."""

    torch.manual_seed(42)

    model, head = build_model(name)
    model = model.to(device)

    loss_function = nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(
        head.parameters(),
        lr=0.001
    )

    weights_dir = (
        REPO_ROOT.parent
        / "datasets"
        / "trained_model_artifacts"
        / source
    )
    weights_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = weights_dir / (
        name.lower().replace("-", "_") + "_best.pth"
    )

    best_f1 = -1.0
    best_balanced_accuracy = -1.0
    best_sensitivity = -1.0
    best_epoch = 0
    best_metrics = None
    history = []

    start = time.perf_counter()

    print(f"\nTRAINING {name}")
    print("-" * 45)

    for epoch in range(epochs):
        # Freeze the pretrained backbone, including BatchNorm statistics.
        # Only the new classifier learns.
        model.eval()
        head.train()

        total_loss = 0.0

        for images, labels in loaders["train"]:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()

            outputs = model(images)
            loss = loss_function(outputs, labels)

            loss.backward()
            optimizer.step()

            total_loss += loss.item() * images.size(0)

        train_loss = (
            total_loss / len(loaders["train"].dataset)
        )

        metrics = evaluate(
            model,
            loaders["validation"],
            device
        )

        history.append({
            "Model": name,
            "Epoch": epoch + 1,
            "Train_Loss": train_loss,
            "Val_Accuracy": metrics["Accuracy"],
            "Val_F1": metrics["F1"],
            "Val_Sensitivity": metrics["Sensitivity"],
            "Val_Specificity": metrics["Specificity"],
        })

        print(
            f"Epoch {epoch + 1}/{epochs} | "
            f"Loss: {train_loss:.4f} | "
            f"Acc: {metrics['Accuracy']:.4f} | "
            f"F1: {metrics['F1']:.4f} | "
            f"Sensitivity: {metrics['Sensitivity']:.4f}"
        )

        improved = (
            metrics["Balanced_Accuracy"] > best_balanced_accuracy
            or (
                metrics["Balanced_Accuracy"] == best_balanced_accuracy
                and metrics["F1"] > best_f1
            )
        )

        if improved:
            best_f1 = metrics["F1"]
            best_balanced_accuracy = metrics["Balanced_Accuracy"]
            best_sensitivity = metrics["Sensitivity"]
            best_epoch = epoch + 1
            best_metrics = metrics.copy()

            torch.save(model.state_dict(), checkpoint)

    elapsed = time.perf_counter() - start

    print(
        f"Best epoch: {best_epoch} | "
        f"Balanced Accuracy: {best_balanced_accuracy:.4f} | "
        f"Best F1: {best_f1:.4f}"
    )

    result = {
        "Model": name,
        "Best_Epoch": best_epoch,
        "Val_Accuracy": best_metrics["Accuracy"],
        "Val_Balanced_Accuracy": best_metrics["Balanced_Accuracy"],
        "Val_F1": best_metrics["F1"],
        "Val_Sensitivity": best_metrics["Sensitivity"],
        "Val_Specificity": best_metrics["Specificity"],
        "Training_Seconds": round(elapsed, 2),
    }

    del model

    if device.type == "cuda":
        torch.cuda.empty_cache()

    return result, history


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        required=True,
        choices=["ghana_conjunctiva", "ghana_fingernail"]
    )
    parser.add_argument("--epochs", type=int, default=5)

    args = parser.parse_args()

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("AYURAI - CNN MODEL COMPARISON")
    print("Dataset:", args.source)
    print("Device:", device)

    if device.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))

    loaders = create_loaders(args.source, batch_size=16)

    models = [
        "MobileNetV2",
        "EfficientNet-B0",
        "ResNet-50"
    ]

    report_dir = (
        REPO_ROOT / "component1"
        / "evaluation" / "images" / args.source
    )
    report_dir.mkdir(parents=True, exist_ok=True)

    results = []
    histories = []

    for name in models:
        result, history = train_model(
            name, loaders, args.source, args.epochs, device
        )

        results.append(result)
        histories.extend(history)

        # Save progress after each model finishes
        pd.DataFrame(results).to_csv(
            report_dir / "validation_comparison.csv",
            index=False
        )
        pd.DataFrame(histories).to_csv(
            report_dir / "training_history.csv",
            index=False
        )

    print("\nFINAL VALIDATION COMPARISON")
    print("-" * 50)

    comparison = pd.DataFrame(results).sort_values(
        ["Val_Balanced_Accuracy", "Val_F1"],
        ascending=False
    )

    print(comparison.to_string(index=False))

    comparison.to_csv(
        report_dir / "validation_comparison.csv",
        index=False
    )

    print("\nReports saved to:", report_dir)
    print("Best model weights saved outside Git.")
    print("Held-out test data has not been used.")


if __name__ == "__main__":
    main()
