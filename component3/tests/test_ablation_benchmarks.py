"""AyurAI Component 3: Unit Tests for Ablation Benchmarking & Evaluation Suite."""

import json
from pathlib import Path
import sys
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.metrics import (
    compute_classification_metrics,
    compute_multiclass_brier_score,
    compute_specificity_scores,
    compute_stratified_subgroups,
)

ARTIFACTS_DIR = BASE_DIR / "artifacts"


def test_metrics_calculation_and_brier_score():
    y_true = [0, 1, 2, 0, 1, 2]
    y_pred = [0, 1, 2, 0, 2, 2]
    y_prob = [
        [0.8, 0.1, 0.1],
        [0.1, 0.8, 0.1],
        [0.1, 0.1, 0.8],
        [0.7, 0.2, 0.1],
        [0.2, 0.3, 0.5],
        [0.1, 0.2, 0.7],
    ]

    metrics = compute_classification_metrics(y_true, y_pred, y_prob)

    assert metrics["sample_count"] == 6
    assert metrics["accuracy"] == round(5 / 6, 4)
    assert metrics["macro_f1"] > 0.70
    assert metrics["macro_specificity"] > 0.75
    assert metrics["brier_score"] is not None
    assert metrics["brier_score"] < 0.50  # Low calibration error
    assert "Safe" in metrics["per_class"]
    assert "High Risk" in metrics["per_class"]


def test_subgroup_stratification():
    evaluations = [
        {
            "patient_context": {
                "age": 70,
                "egfr": 35.0,  # Renal
                "alt": 25.0,
                "pregnancy": False,
                "comorbidities": ["Hypertension"],
                "concurrent_drugs": ["Amlodipine", "Atorvastatin", "Metformin"],  # Polypharmacy
            }
        },
        {
            "patient_context": {
                "age": 30,
                "egfr": 95.0,
                "alt": 110.0,  # Hepatic
                "pregnancy": True,  # Pregnant
                "comorbidities": [],
                "concurrent_drugs": ["Paracetamol"],
            }
        },
    ]

    y_true = [2, 1]
    y_pred = [2, 1]
    y_prob = [[0.05, 0.15, 0.80], [0.10, 0.80, 0.10]]

    subgroups = compute_stratified_subgroups(evaluations, y_true, y_pred, y_prob)

    assert "Overall Cohort" in subgroups
    assert "Renal Impairment (eGFR < 60)" in subgroups
    assert "Elderly (Age >= 65)" in subgroups
    assert "Polypharmacy (>= 3 co-medications)" in subgroups
    assert "Pregnant / Trimester 1-3" in subgroups
    assert subgroups["Renal Impairment (eGFR < 60)"]["sample_count"] == 1
    assert subgroups["Pregnant / Trimester 1-3"]["sample_count"] == 1


def test_benchmark_results_json_structure():
    bench_file = ARTIFACTS_DIR / "benchmark_results.json"
    assert bench_file.exists(), "benchmark_results.json artifact not found"

    with open(bench_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "held_out_test_set" in data
    assert "full_cohort" in data
    assert "subgroup_stratification" in data

    test_models = data["held_out_test_set"]
    assert "M1: Heuristic Rules Alone" in test_models
    assert "M2: Static GNN Link Alone" in test_models
    assert "M3: Naive Context (Concatenation)" in test_models
    assert "M4: Proposed Context Fusion (Ours)" in test_models

    # Verify M4 outperforms M3 on Macro-F1 by a wide margin
    m3_f1 = test_models["M3: Naive Context (Concatenation)"]["macro_f1"]
    m4_f1 = test_models["M4: Proposed Context Fusion (Ours)"]["macro_f1"]
    assert m4_f1 > m3_f1, f"Expected M4 Macro-F1 ({m4_f1}) > M3 ({m3_f1})"
    assert m4_f1 >= 0.80, f"Expected M4 Macro-F1 >= 0.80, got {m4_f1}"


def test_dissertation_tables_generation():
    md_file = ARTIFACTS_DIR / "dissertation_tables.md"
    tex_file = ARTIFACTS_DIR / "dissertation_tables.tex"
    svg_file = ARTIFACTS_DIR / "roc_pr_curves.svg"

    assert md_file.exists(), "dissertation_tables.md not found"
    assert tex_file.exists(), "dissertation_tables.tex not found"
    assert svg_file.exists(), "roc_pr_curves.svg not found"

    with open(md_file, "r", encoding="utf-8") as f:
        md_text = f.read()
    assert "Table 5.1" in md_text
    assert "M4" in md_text

    with open(tex_file, "r", encoding="utf-8") as f:
        tex_text = f.read()
    assert r"\begin{table*}" in tex_text
    assert "tab:ablation_primary_results" in tex_text
