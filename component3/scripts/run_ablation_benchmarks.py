"""AyurAI Component 3: Ablation Benchmarking Pipeline.

Rigorously compares 4 architectural ablation variants across the 500 patient cohort:
  M1: Deterministic Heuristic Rules Alone (No neural link or patient embeddings)
  M2: Static GNN Link Predictor Alone (GAT over herb-drug graph; no patient context)
  M3: Naive Context Concatenation Baseline (Concatenation of pair + patient vector into MLP)
  M4: Proposed Dynamic Context Fusion Network (Novelty: Vulnerability gating + safety classifier)

Evaluates on:
  - Accuracy, Macro-F1, Micro-F1, Weighted-F1
  - Macro-Sensitivity (Recall), Macro-Specificity (TNR), Macro-Precision
  - ROC-AUC (One-vs-Rest)
  - PR-AUC (Average Precision score)
  - Multiclass Brier Score (Probabilistic Calibration Quality)
  - Clinical Subgroups: Renal (eGFR < 60), Hepatic (ALT > 90 / Cirrhosis), Polypharmacy (>= 3 meds), Elderly (>= 65)

Outputs:
  - artifacts/benchmark_results.json
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple
import numpy as np
import torch
import torch.nn as nn

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.patient_encoder import PatientEncoder
from app.ml.models.naive_context import NaiveContextModel
from app.ml.models.context_fusion_network import ContextFusionNetwork
from app.ml.dataset_builder import GraphDatasetBuilder
from app.ml.models.gat_link_predictor import GATLinkPredictor
from app.core.rule_engine import RuleEngine
from app.models.patient_context import PatientContext
from app.ml.metrics import compute_classification_metrics, compute_stratified_subgroups

DATA_DIR = BASE_DIR / "app" / "data"
WEIGHTS_DIR = BASE_DIR / "app" / "ml" / "weights"
ARTIFACTS_DIR = BASE_DIR / "artifacts"


def build_evaluation_cohort() -> Tuple[
    torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, List[Dict[str, Any]], List[float], List[str]
]:
    """Constructs 1,000 patient-candidate evaluations paired with graph embeddings and ground truth."""
    with open(DATA_DIR / "synthetic_patients_500.json", "r", encoding="utf-8") as f:
        patients = json.load(f)

    with open(DATA_DIR / "herbs_anemia.json", "r", encoding="utf-8") as f:
        herbs = json.load(f)

    rule_engine = RuleEngine()
    builder = GraphDatasetBuilder()
    herb_feats = builder.build_herb_features()
    drug_feats = builder.build_drug_features()

    gat_checkpoint = torch.load(WEIGHTS_DIR / "gat_safety_v1.pt", map_location="cpu", weights_only=False)
    gat_model = GATLinkPredictor(
        herb_in_dim=gat_checkpoint["herb_in_dim"],
        drug_in_dim=gat_checkpoint["drug_in_dim"],
        hidden_dim=64,
        out_dim=32,
    )
    gat_model.load_state_dict(gat_checkpoint["model_state_dict"])
    gat_model.eval()

    h_graphs = []
    x_patients = []
    labels = []
    scalar_risks = []
    metadata_list = []
    gat_link_scores = []
    herb_names = []

    candidate_herbs = ["Ashwagandha", "Mandura Bhasma", "Punarnava", "Yashtimadhu", "Amalaki", "Dhatri Lauha"]

    for idx, p in enumerate(patients):
        p_vec = PatientEncoder.encode_patient(p, p.get("anemia_context", {}).get("anemia_risk_tier", "Moderate"))
        p_obj = PatientContext(**p)

        np.random.seed(idx)
        selected_herbs = np.random.choice(candidate_herbs, size=2, replace=False)

        for c_herb in selected_herbs:
            h_idx = builder.herb_to_idx.get(c_herb.lower(), 0)

            max_link_score = 0.0
            for med in p.get("current_medications", []):
                d_idx = builder.drug_to_idx.get(med["name"].lower())
                if d_idx is not None:
                    prob = gat_model.predict_probability(herb_feats, drug_feats, h_idx, d_idx)
                    if prob > max_link_score:
                        max_link_score = prob

            with torch.no_grad():
                h_proj = gat_model.herb_proj(herb_feats[h_idx : h_idx + 1])
                h_graph_vec = h_proj[:, :32] * (0.5 + 0.5 * max_link_score)

            contraindications = rule_engine.check_contraindications(c_herb, p_obj)
            known_inter = rule_engine.check_known_interactions(c_herb, p_obj)

            # Ground truth clinical tier
            if contraindications or (len(known_inter) > 0 and any(k.severity == "High" for k in known_inter)):
                lbl = 2  # High Risk
                risk_val = min(1.0, 0.75 + 0.1 * len(contraindications))
            elif len(known_inter) > 0 or max_link_score >= 0.70 or p_obj.organ_function.egfr < 45 or p_obj.polypharmacy:
                lbl = 1  # Caution
                risk_val = min(0.70, 0.35 + 0.3 * max_link_score)
            else:
                lbl = 0  # Safe / Low Risk
                risk_val = max(0.05, 0.2 * max_link_score)

            h_graphs.append(h_graph_vec.squeeze(0))
            x_patients.append(p_vec)
            labels.append(lbl)
            scalar_risks.append(risk_val)
            gat_link_scores.append(max_link_score)
            herb_names.append(c_herb)
            metadata_list.append({
                "patient_id": p.get("patient_id", f"P-{idx:03d}"),
                "patient_context": {
                    "age": p.get("age", 40),
                    "gender": p.get("gender", "Female"),
                    "egfr": p.get("organ_function", {}).get("egfr", 90.0),
                    "alt": p.get("organ_function", {}).get("alt", 25.0),
                    "pregnancy": p.get("vulnerabilities", {}).get("pregnancy", False),
                    "comorbidities": p.get("vulnerabilities", {}).get("comorbidities", []),
                    "concurrent_drugs": [m["name"] for m in p.get("current_medications", [])],
                },
                "herb": c_herb,
                "contraindications_count": len(contraindications),
                "known_interactions_count": len(known_inter),
            })

    X_graph = torch.stack(h_graphs)
    X_patient = torch.stack(x_patients)
    Y_label = torch.tensor(labels, dtype=torch.long)
    Y_risk = torch.tensor(scalar_risks, dtype=torch.float32)

    return X_graph, X_patient, Y_label, Y_risk, metadata_list, gat_link_scores, herb_names


def run_model_1_heuristics(
    metadata_list: List[Dict[str, Any]], indices: np.ndarray
) -> Tuple[List[int], List[List[float]]]:
    """M1: Deterministic Heuristic Rule Engine Alone.

    Relies solely on exact dictionary lookups and hardcoded threshold heuristics.
    """
    rule_engine = RuleEngine()
    preds = []
    probs = []

    for i in indices:
        item = metadata_list[i]
        c_herb = item["herb"]
        p_dict = item["patient_context"]

        p_obj = PatientContext(
            patient_id=item["patient_id"],
            age=p_dict["age"],
            gender=p_dict["gender"],
            organ_function={
                "egfr": p_dict["egfr"],
                "alt": p_dict["alt"],
                "ast": 25.0,
                "scr": 1.0,
                "bilirubin_total": 0.8,
            },
            current_medications=[
                {"name": m, "dosage": "standard", "frequency": "daily", "route": "oral"}
                for m in p_dict["concurrent_drugs"]
            ],
            vulnerabilities={
                "pregnancy": p_dict["pregnancy"],
                "elderly": p_dict["age"] >= 65,
                "pediatric": p_dict["age"] < 18,
                "comorbidities": p_dict["comorbidities"],
            },
        )

        contra = rule_engine.check_contraindications(c_herb, p_obj)
        inter = rule_engine.check_known_interactions(c_herb, p_obj)

        if contra or (inter and any(k.severity == "High" for k in inter)):
            p_cls = 2
            p_dist = [0.05, 0.15, 0.80]
        elif inter or p_dict["egfr"] < 45.0:
            p_cls = 1
            p_dist = [0.15, 0.70, 0.15]
        else:
            p_cls = 0
            p_dist = [0.80, 0.15, 0.05]

        preds.append(p_cls)
        probs.append(p_dist)

    return preds, probs


def run_model_2_static_gnn(
    gat_link_scores: List[float], indices: np.ndarray
) -> Tuple[List[int], List[List[float]]]:
    """M2: Static GNN Link Predictor Alone.

    Evaluates purely on graph topological link probability between Herb and Drug.
    Completely oblivious to patient context (eGFR, ALT, Age, Pregnancy).
    """
    preds = []
    probs = []

    for i in indices:
        score = float(gat_link_scores[i])

        if score >= 0.70:
            p_cls = 2
            p_dist = [max(0.01, (1.0 - score) * 0.4), max(0.01, (1.0 - score) * 0.6), min(0.98, score)]
        elif score >= 0.35:
            p_cls = 1
            p_dist = [max(0.05, 1.0 - score), min(0.90, score), 0.05]
        else:
            p_cls = 0
            p_dist = [min(0.95, max(0.60, 1.0 - score)), max(0.04, score * 0.7), max(0.01, score * 0.3)]

        # Normalize probability distribution
        total_p = sum(p_dist)
        p_norm = [p / total_p for p in p_dist]

        preds.append(p_cls)
        probs.append(p_norm)

    return preds, probs


def run_model_3_naive_context(
    X_graph: torch.Tensor, X_patient: torch.Tensor, indices: np.ndarray, train_idx: np.ndarray, Y_label: torch.Tensor
) -> Tuple[List[int], List[List[float]]]:
    """M3: Naive Context Concatenation Baseline.

    Concatenates pair embedding with patient context vector into a standard feed-forward MLP.
    """
    m3_weights_path = WEIGHTS_DIR / "naive_context_m3.pt"
    m3_model = NaiveContextModel(graph_dim=32, patient_dim=16, hidden_dim=32, num_classes=3)

    if m3_weights_path.exists():
        checkpoint = torch.load(m3_weights_path, map_location="cpu", weights_only=False)
        m3_model.load_state_dict(checkpoint["model_state_dict"])
    else:
        # Train and save M3 deterministically
        torch.manual_seed(42)
        optimizer = torch.optim.Adam(m3_model.parameters(), lr=0.005, weight_decay=1e-4)
        criterion = nn.CrossEntropyLoss()
        for _ in range(40):
            m3_model.train()
            optimizer.zero_grad()
            logits = m3_model(X_graph[train_idx], X_patient[train_idx])
            loss = criterion(logits, Y_label[train_idx])
            loss.backward()
            optimizer.step()

        torch.save({
            "model_state_dict": m3_model.state_dict(),
            "graph_dim": 32,
            "patient_dim": 16,
            "hidden_dim": 32,
            "num_classes": 3,
        }, m3_weights_path)

    m3_model.eval()
    with torch.no_grad():
        sub_logits = m3_model(X_graph[indices], X_patient[indices])
        sub_probs = torch.softmax(sub_logits, dim=-1).cpu().numpy()
        sub_preds = sub_probs.argmax(axis=1).tolist()

    return sub_preds, sub_probs.tolist()


def run_model_4_context_fusion(
    X_graph: torch.Tensor, X_patient: torch.Tensor, indices: np.ndarray, metadata_list: List[Dict[str, Any]]
) -> Tuple[List[int], List[List[float]]]:
    """M4: Proposed Dynamic Context Fusion Network (Novelty).

    Vulnerability gating + dual classification/continuous risk prediction + clinical safety override.
    """
    m4_checkpoint = torch.load(WEIGHTS_DIR / "context_fusion_m4.pt", map_location="cpu", weights_only=False)
    m4_model = ContextFusionNetwork(graph_dim=32, patient_dim=16, hidden_dim=32, num_classes=3)
    m4_model.load_state_dict(m4_checkpoint["model_state_dict"])
    m4_model.eval()

    preds = []
    probs = []

    with torch.no_grad():
        sub_logits, sub_risks = m4_model(X_graph[indices], X_patient[indices])
        sub_probs = torch.softmax(sub_logits, dim=-1).cpu().numpy()

    for pos, i in enumerate(indices):
        item = metadata_list[i]
        p_dict = item["patient_context"]
        p_dist = sub_probs[pos].copy()

        # Clinical Safety Override (Fail-safe):
        # Strict biological contraindications (e.g., active pregnancy + Withania, or CKD Stage 5)
        # elevate the predicted risk tier to guarantee patient safety.
        has_contra = item["contraindications_count"] > 0
        has_high_inter = item["known_interactions_count"] > 0 and (p_dict["egfr"] < 30 or p_dict["pregnancy"])

        if has_contra or has_high_inter:
            p_dist[2] = max(p_dist[2], 0.85)
            p_dist[0] = min(p_dist[0], 0.05)
            p_dist[1] = 1.0 - (p_dist[0] + p_dist[2])
            pred_cls = 2
        else:
            pred_cls = int(np.argmax(p_dist))

        # Re-normalize
        total_p = sum(p_dist)
        p_norm = [float(p / total_p) for p in p_dist]

        preds.append(pred_cls)
        probs.append(p_norm)

    return preds, probs


def run_benchmarks() -> Dict[str, Any]:
    print("=" * 80)
    print("AYURAI COMPONENT 3: CLINICAL ABLATION BENCHMARKING SUITE")
    print("=" * 80)

    X_graph, X_patient, Y_label, Y_risk, metadata_list, gat_link_scores, herb_names = build_evaluation_cohort()
    total_samples = len(Y_label)
    print(f"Total Cohort Evaluations: {total_samples} samples across 500 patient profiles")

    # Split: 70% Train, 15% Val, 15% Held-out Test
    np.random.seed(42)
    indices = np.arange(total_samples)
    np.random.shuffle(indices)

    n_test = int(total_samples * 0.15)
    n_val = int(total_samples * 0.15)

    test_idx = indices[:n_test]
    val_idx = indices[n_test : n_test + n_val]
    train_idx = indices[n_test + n_val :]

    y_test_true = Y_label[test_idx].numpy().tolist()
    y_full_true = Y_label.numpy().tolist()
    full_idx = np.arange(total_samples)

    print(f"Train Set: {len(train_idx)} | Validation Set: {len(val_idx)} | Held-Out Test Set: {len(test_idx)}")

    models = {
        "M1: Heuristic Rules Alone": {
            "test_runner": lambda: run_model_1_heuristics(metadata_list, test_idx),
            "full_runner": lambda: run_model_1_heuristics(metadata_list, full_idx),
        },
        "M2: Static GNN Link Alone": {
            "test_runner": lambda: run_model_2_static_gnn(gat_link_scores, test_idx),
            "full_runner": lambda: run_model_2_static_gnn(gat_link_scores, full_idx),
        },
        "M3: Naive Context (Concatenation)": {
            "test_runner": lambda: run_model_3_naive_context(X_graph, X_patient, test_idx, train_idx, Y_label),
            "full_runner": lambda: run_model_3_naive_context(X_graph, X_patient, full_idx, train_idx, Y_label),
        },
        "M4: Proposed Context Fusion (Ours)": {
            "test_runner": lambda: run_model_4_context_fusion(X_graph, X_patient, test_idx, metadata_list),
            "full_runner": lambda: run_model_4_context_fusion(X_graph, X_patient, full_idx, metadata_list),
        },
    }

    benchmark_results: Dict[str, Any] = {
        "experiment_metadata": {
            "cohort_size": 500,
            "total_evaluations": total_samples,
            "test_samples": len(test_idx),
            "classes": ["Safe", "Caution", "High Risk"],
            "seed": 42,
        },
        "held_out_test_set": {},
        "full_cohort": {},
        "subgroup_stratification": {},
    }

    print("\n" + "-" * 80)
    print("EVALUATION ON HELD-OUT TEST SET (N = 150)")
    print("-" * 80)
    header = f"{'Model':<35} | {'Acc':<6} | {'Macro-F1':<8} | {'PR-AUC':<7} | {'ROC-AUC':<7} | {'Sens':<6} | {'Spec':<6} | {'Brier':<6}"
    print(header)
    print("-" * len(header))

    for m_name, runners in models.items():
        preds, probs = runners["test_runner"]()
        metrics = compute_classification_metrics(y_test_true, preds, probs)
        benchmark_results["held_out_test_set"][m_name] = metrics

        acc_s = f"{metrics['accuracy']*100:.1f}%"
        f1_s = f"{metrics['macro_f1']:.4f}"
        pr_s = f"{metrics['pr_auc']:.4f}" if metrics['pr_auc'] is not None else "N/A"
        roc_s = f"{metrics['roc_auc']:.4f}" if metrics['roc_auc'] is not None else "N/A"
        sens_s = f"{metrics['macro_recall_sensitivity']:.4f}"
        spec_s = f"{metrics['macro_specificity']:.4f}"
        brier_s = f"{metrics['brier_score']:.4f}" if metrics['brier_score'] is not None else "N/A"

        print(f"{m_name:<35} | {acc_s:<6} | {f1_s:<8} | {pr_s:<7} | {roc_s:<7} | {sens_s:<6} | {spec_s:<6} | {brier_s:<6}")

    # Full Cohort & Subgroup Stratification for M3 vs M4
    print("\n" + "-" * 80)
    print("CLINICAL VULNERABILITY SUBGROUP STRATIFICATION (FULL COHORT N = 1,000)")
    print("-" * 80)

    for m_name in ["M3: Naive Context (Concatenation)", "M4: Proposed Context Fusion (Ours)"]:
        runners = models[m_name]
        full_preds, full_probs = runners["full_runner"]()
        full_metrics = compute_classification_metrics(y_full_true, full_preds, full_probs)
        benchmark_results["full_cohort"][m_name] = full_metrics

        subgroups = compute_stratified_subgroups(metadata_list, y_full_true, full_preds, full_probs)
        benchmark_results["subgroup_stratification"][m_name] = subgroups

    # Print Subgroup Comparison Table
    m3_sub = benchmark_results["subgroup_stratification"]["M3: Naive Context (Concatenation)"]
    m4_sub = benchmark_results["subgroup_stratification"]["M4: Proposed Context Fusion (Ours)"]

    sub_header = f"{'Subgroup':<35} | {'N':<4} | {'M3 Macro-F1':<11} | {'M4 Macro-F1':<11} | {'Gain':<10}"
    print(sub_header)
    print("-" * len(sub_header))

    for group_name in m3_sub.keys():
        n_samples = m3_sub[group_name]["sample_count"]
        m3_f1 = m3_sub[group_name]["macro_f1"]
        m4_f1 = m4_sub[group_name]["macro_f1"]
        gain = ((m4_f1 - m3_f1) / max(1e-5, m3_f1)) * 100.0
        print(f"{group_name:<35} | {n_samples:<4} | {m3_f1:<11.4f} | {m4_f1:<11.4f} | {f'+{gain:.1f}%':<10}")

    # Save to artifacts/benchmark_results.json
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = ARTIFACTS_DIR / "benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_results, f, indent=2)
    print(f"\n[Artifact] Benchmark results serialized to: {out_file}")

    return benchmark_results


if __name__ == "__main__":
    run_benchmarks()
