
# AyurAI Component 1 - Held-out Image Model Evaluation

import argparse

import matplotlib.pyplot as plt
import pandas as pd
import torch

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    recall_score,
    roc_auc_score,
    confusion_matrix,
    ConfusionMatrixDisplay,
    classification_report
)

from catalog_dataset import REPO_ROOT
from make_split_loaders import create_loaders
from train_catalog_models import build_model


def evaluate_test(source):
    """Evaluate the validation-selected ResNet-50 checkpoint once."""

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    model_name = "ResNet-50"

    checkpoint = (
        REPO_ROOT.parent
        / "datasets"
        / "trained_model_artifacts"
        / source
        / "resnet_50_best.pth"
    )

    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)

    report_dir = (
        REPO_ROOT
        / "component1"
        / "evaluation"
        / "images"
        / source
    )
    report_dir.mkdir(parents=True, exist_ok=True)

    metrics_file = report_dir / "test_metrics.csv"

    # Prevent accidental repeated test evaluation
    if metrics_file.exists():
        raise FileExistsError(
            f"Test results already exist: {metrics_file}"
        )

    loaders = create_loaders(source, batch_size=16)

    model, _ = build_model(model_name)

    model.load_state_dict(
        torch.load(
            checkpoint,
            map_location=device,
            weights_only=True
        )
    )

    model = model.to(device)
    model.eval()

    y_true = []
    y_pred = []
    y_prob = []

    with torch.inference_mode():
        for images, labels in loaders["test"]:
            images = images.to(device)

            outputs = model(images)
            probabilities = torch.softmax(outputs, dim=1)

            predictions = probabilities.argmax(dim=1)

            y_true.extend(labels.tolist())
            y_pred.extend(predictions.cpu().tolist())
            y_prob.extend(probabilities[:, 1].cpu().tolist())

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    results = {
        "Source": source,
        "Model": model_name,
        "Test_Images": len(y_true),
        "Accuracy": accuracy_score(y_true, y_pred),
        "Balanced_Accuracy": balanced_accuracy_score(
            y_true, y_pred
        ),
        "Sensitivity": recall_score(
            y_true, y_pred, pos_label=1, zero_division=0
        ),
        "Specificity": recall_score(
            y_true, y_pred, pos_label=0, zero_division=0
        ),
        "F1": f1_score(y_true, y_pred, zero_division=0),
        "AUROC": roc_auc_score(y_true, y_prob),
        "True_Negatives": int(tn),
        "False_Positives": int(fp),
        "False_Negatives": int(fn),
        "True_Positives": int(tp)
    }

    print("\nAYURAI - HELD-OUT TEST RESULTS")
    print("-" * 45)

    for key, value in results.items():
        print(f"{key}: {value}")

    report = classification_report(
        y_true,
        y_pred,
        labels=[0, 1],
        target_names=["Non-anaemic", "Anaemic"],
        zero_division=0
    )

    print("\nClassification report:")
    print(report)

    # Save classification report
    (report_dir / "test_classification_report.txt").write_text(
        report,
        encoding="utf-8"
    )

    # Plot and save confusion matrix
    fig, ax = plt.subplots(figsize=(6, 5))

    ConfusionMatrixDisplay(
        confusion_matrix=cm,
        display_labels=["Non-anaemic", "Anaemic"]
    ).plot(
        ax=ax,
        cmap="Blues",
        values_format="d"
    )

    ax.set_title(f"{source} - ResNet-50 Test Results")

    fig.tight_layout()
    fig.savefig(
        report_dir / "test_confusion_matrix.png",
        dpi=200
    )

    plt.show()
    plt.close(fig)

    # Save metrics last, marking evaluation as completed
    pd.DataFrame([results]).to_csv(
        metrics_file,
        index=False
    )

    print("\nTest evaluation completed!")
    print("Reports saved to:", report_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        required=True,
        choices=["ghana_conjunctiva", "ghana_fingernail"]
    )

    args = parser.parse_args()

    evaluate_test(args.source)
