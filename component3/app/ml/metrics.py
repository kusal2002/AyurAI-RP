"""AyurAI Component 3: Clinical ML Evaluation Metrics Suite.

Computes comprehensive clinical safety evaluation metrics:
- Accuracy, Precision, Recall / Sensitivity, Specificity
- Macro-F1, Micro-F1, Weighted-F1
- ROC-AUC (One-vs-Rest)
- PR-AUC (Average Precision Score across precision-recall curve)
- Multiclass Brier Score (Probabilistic Calibration Quality)
- Subgroup stratification (Renal, Hepatic, Polypharmacy, Elderly)
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize


def compute_multiclass_brier_score(y_true: np.ndarray, y_prob: np.ndarray, num_classes: int = 3) -> float:
    """Computes multiclass Brier Score (mean squared difference between

    predicted probability vector and one-hot true indicator vector).
    Lower is better (0.0 = perfect calibration).
    """
    if len(y_true) == 0:
        return 0.0
    y_true_onehot = label_binarize(y_true, classes=list(range(num_classes)))
    if num_classes == 2 and y_true_onehot.shape[1] == 1:
        y_true_onehot = np.hstack([1 - y_true_onehot, y_true_onehot])
    return float(np.mean(np.sum((y_prob - y_true_onehot) ** 2, axis=1)))


def compute_specificity_scores(cm: np.ndarray) -> Dict[str, float]:
    """Computes specificity (True Negative Rate) for each class and macro-average

    from a multiclass confusion matrix.
    Specificity = TN / (TN + FP)
    """
    num_classes = cm.shape[0]
    specificities = []
    per_class = {}

    for i in range(num_classes):
        tp = cm[i, i]
        fn = np.sum(cm[i, :]) - tp
        fp = np.sum(cm[:, i]) - tp
        tn = np.sum(cm) - (tp + fn + fp)
        spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        specificities.append(spec)
        per_class[f"class_{i}"] = round(spec, 4)

    per_class["macro_specificity"] = round(float(np.mean(specificities)), 4) if specificities else 0.0
    return per_class


def compute_classification_metrics(
    y_true: Union[List[int], np.ndarray],
    y_pred: Union[List[int], np.ndarray],
    y_prob: Optional[Union[List[List[float]], np.ndarray]] = None,
    class_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Computes standard and clinical safety classification metrics.

    Parameters:
        y_true: Ground truth labels (e.g. 0=Safe, 1=Caution, 2=High Risk).
        y_pred: Predicted class labels.
        y_prob: Predicted probability distribution array of shape [N, num_classes].
        class_names: Optional list of class names.

    Returns:
        Dict of computed evaluation metrics.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    if class_names is None:
        class_names = ["Safe", "Caution", "High Risk"]
    num_classes = len(class_names)

    if len(y_true) == 0:
        return {"error": "Empty evaluation dataset"}

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_classes)))
    spec_dict = compute_specificity_scores(cm)

    metrics: Dict[str, Any] = {
        "sample_count": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "micro_f1": round(float(f1_score(y_true, y_pred, average="micro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "macro_precision": round(float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "macro_recall_sensitivity": round(float(recall_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "macro_specificity": spec_dict["macro_specificity"],
        "confusion_matrix": cm.tolist(),
        "per_class": {},
    }

    # Per-class sensitivity (recall) and specificity
    recalls = recall_score(y_true, y_pred, labels=list(range(num_classes)), average=None, zero_division=0)
    precisions = precision_score(y_true, y_pred, labels=list(range(num_classes)), average=None, zero_division=0)
    f1s = f1_score(y_true, y_pred, labels=list(range(num_classes)), average=None, zero_division=0)

    for i, name in enumerate(class_names):
        metrics["per_class"][name] = {
            "precision": round(float(precisions[i]), 4),
            "sensitivity_recall": round(float(recalls[i]), 4),
            "specificity": spec_dict.get(f"class_{i}", 0.0),
            "f1_score": round(float(f1s[i]), 4),
            "support": int(np.sum(y_true == i)),
        }

    # Probabilistic metrics (ROC-AUC, PR-AUC, Brier score)
    if y_prob is not None:
        y_prob = np.asarray(y_prob, dtype=float)
        # Ensure valid 2D shape
        if y_prob.ndim == 1:
            y_prob = np.vstack([1 - y_prob, y_prob]).T

        metrics["brier_score"] = round(compute_multiclass_brier_score(y_true, y_prob, num_classes=num_classes), 4)

        try:
            # Multi-class ROC-AUC One-vs-Rest
            y_true_bin = label_binarize(y_true, classes=list(range(num_classes)))
            if num_classes == 2 and y_true_bin.shape[1] == 1:
                roc_auc = roc_auc_score(y_true, y_prob[:, 1])
                pr_auc = average_precision_score(y_true, y_prob[:, 1])
            else:
                roc_auc = roc_auc_score(y_true_bin, y_prob, multi_class="ovr", average="macro")
                pr_auc = average_precision_score(y_true_bin, y_prob, average="macro")
            metrics["roc_auc"] = round(float(roc_auc), 4)
            metrics["pr_auc"] = round(float(pr_auc), 4)
        except Exception:
            metrics["roc_auc"] = None
            metrics["pr_auc"] = None
    else:
        metrics["brier_score"] = None
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None

    return metrics


def compute_stratified_subgroups(
    evaluations: List[Dict[str, Any]],
    y_true: List[int],
    y_pred: List[int],
    y_prob: Optional[List[List[float]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Splits cohort evaluations into clinical risk subgroups and evaluates metrics per subgroup:

    - Renal Impairment (eGFR < 60 mL/min)
    - Hepatic Impairment (ALT > 90 U/L or Cirrhosis)
    - Polypharmacy (Active concurrent medications >= 3)
    - Elderly Cohort (Age >= 65)
    - General Adult Baseline
    """
    subgroup_indices: Dict[str, List[int]] = {
        "Overall Cohort": list(range(len(evaluations))),
        "Renal Impairment (eGFR < 60)": [],
        "Hepatic Impairment (ALT > 90 / Cirrhosis)": [],
        "Polypharmacy (>= 3 co-medications)": [],
        "Elderly (Age >= 65)": [],
        "Pregnant / Trimester 1-3": [],
    }

    for idx, item in enumerate(evaluations):
        ctx = item.get("patient_context", {})
        egfr = ctx.get("egfr", 90.0)
        alt = ctx.get("alt", 25.0)
        age = ctx.get("age", 40)
        preg = ctx.get("pregnancy", False)
        co_meds = ctx.get("concurrent_drugs", [])
        cirrhosis = "cirrhosis" in [c.lower() for c in ctx.get("comorbidities", [])]

        if egfr < 60.0:
            subgroup_indices["Renal Impairment (eGFR < 60)"].append(idx)
        if alt > 90.0 or cirrhosis:
            subgroup_indices["Hepatic Impairment (ALT > 90 / Cirrhosis)"].append(idx)
        if len(co_meds) >= 3:
            subgroup_indices["Polypharmacy (>= 3 co-medications)"].append(idx)
        if age >= 65:
            subgroup_indices["Elderly (Age >= 65)"].append(idx)
        if preg:
            subgroup_indices["Pregnant / Trimester 1-3"].append(idx)

    subgroup_results = {}
    y_prob_arr = np.asarray(y_prob) if y_prob is not None else None

    for name, indices in subgroup_indices.items():
        if not indices:
            continue
        sub_true = [y_true[i] for i in indices]
        sub_pred = [y_pred[i] for i in indices]
        sub_prob = y_prob_arr[indices] if y_prob_arr is not None else None
        res = compute_classification_metrics(sub_true, sub_pred, sub_prob)
        subgroup_results[name] = res

    return subgroup_results
