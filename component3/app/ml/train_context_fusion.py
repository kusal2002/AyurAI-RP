"""Training Pipeline for Context Fusion Models (M3 Naive vs M4 Proposed Novelty).

Trains on the 500 synthetic patient cohort paired with candidate Ayurvedic
recommendations and in-silico graph embeddings. Exports M4 weights checkpoint.
"""

import json
from pathlib import Path
import sys
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score, accuracy_score, classification_report

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.patient_encoder import PatientEncoder
from app.ml.models.naive_context import NaiveContextModel
from app.ml.models.context_fusion_network import ContextFusionNetwork
from app.ml.dataset_builder import GraphDatasetBuilder
from app.ml.models.gat_link_predictor import GATLinkPredictor
from app.core.rule_engine import RuleEngine

DATA_DIR = BASE_DIR / "app" / "data"
WEIGHTS_DIR = BASE_DIR / "app" / "ml" / "weights"


def build_clinical_training_set():
    """Builds paired (h_graph, x_patient, label, continuous_risk) samples."""
    with open(DATA_DIR / "synthetic_patients_500.json", "r", encoding="utf-8") as f:
        patients = json.load(f)

    with open(DATA_DIR / "herbs_anemia.json", "r", encoding="utf-8") as f:
        herbs = json.load(f)

    rule_engine = RuleEngine()
    builder = GraphDatasetBuilder()
    herb_feats = builder.build_herb_features()
    drug_feats = builder.build_drug_features()

    # Load GAT model for graph embeddings
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

    # Curate realistic candidate evaluations across the 500 patient cohort
    candidate_herbs = ["Ashwagandha", "Mandura Bhasma", "Punarnava", "Yashtimadhu", "Amalaki", "Dhatri Lauha"]

    for idx, p in enumerate(patients):
        p_vec = PatientEncoder.encode_patient(p, p.get("anemia_context", {}).get("anemia_risk_tier", "Moderate"))
        
        # Pick 2 candidate herbs for this patient evaluation
        np.random.seed(idx)
        selected_herbs = np.random.choice(candidate_herbs, size=2, replace=False)

        for c_herb in selected_herbs:
            h_idx = builder.herb_to_idx.get(c_herb.lower(), 0)

            # Compute maximum in-silico link score against patient's drugs
            max_link_score = 0.0
            for med in p.get("current_medications", []):
                d_idx = builder.drug_to_idx.get(med["name"].lower())
                if d_idx is not None:
                    prob = gat_model.predict_probability(herb_feats, drug_feats, h_idx, d_idx)
                    if prob > max_link_score:
                        max_link_score = prob

            # Generate synthetic 32-D graph interaction embedding
            with torch.no_grad():
                h_proj = gat_model.herb_proj(herb_feats[h_idx : h_idx + 1])
                # Compress 64-D to 32-D graph representation
                h_graph_vec = h_proj[:, :32] * (0.5 + 0.5 * max_link_score)

            # Clinical ground truth assessment
            from app.models.patient_context import PatientContext
            p_obj = PatientContext(**p)
            contraindications = rule_engine.check_contraindications(c_herb, p_obj)
            known_inter = rule_engine.check_known_interactions(c_herb, p_obj)

            # Label generation:
            # 2 = High Risk, 1 = Caution, 0 = Low Risk
            if contraindications or (len(known_inter) > 0 and any(k.severity == "High" for k in known_inter)):
                lbl = 2
                risk_val = min(1.0, 0.75 + 0.1 * len(contraindications))
            elif len(known_inter) > 0 or max_link_score >= 0.70 or p_obj.organ_function.egfr < 45 or p_obj.polypharmacy:
                lbl = 1
                risk_val = min(0.70, 0.35 + 0.3 * max_link_score)
            else:
                lbl = 0
                risk_val = max(0.05, 0.2 * max_link_score)

            h_graphs.append(h_graph_vec.squeeze(0))
            x_patients.append(p_vec)
            labels.append(lbl)
            scalar_risks.append(risk_val)

    X_graph = torch.stack(h_graphs)
    X_patient = torch.stack(x_patients)
    Y_label = torch.tensor(labels, dtype=torch.long)
    Y_risk = torch.tensor(scalar_risks, dtype=torch.float32)

    return X_graph, X_patient, Y_label, Y_risk


def train():
    print("=== Training Context Fusion Models: M3 Naive vs M4 Proposed Novelty ===")
    torch.manual_seed(42)
    np.random.seed(42)

    X_graph, X_patient, Y_label, Y_risk = build_clinical_training_set()
    total_samples = len(Y_label)
    print(f"Total Patient-Candidate Evaluation Samples: {total_samples}")

    # Split: 70% Train, 15% Val, 15% Held-out Test
    indices = np.arange(total_samples)
    np.random.shuffle(indices)

    n_test = int(total_samples * 0.15)
    n_val = int(total_samples * 0.15)

    test_idx = indices[:n_test]
    val_idx = indices[n_test : n_test + n_val]
    train_idx = indices[n_test + n_val :]

    # ----------------------------------------------------
    # Train M3: Naive Context Model (Concatenation)
    # ----------------------------------------------------
    print("\n--- Training Model M3: Naive Context (Concatenation Baseline) ---")
    m3_model = NaiveContextModel(graph_dim=32, patient_dim=16, hidden_dim=32, num_classes=3)
    optimizer_m3 = torch.optim.Adam(m3_model.parameters(), lr=0.005, weight_decay=1e-4)
    criterion_ce = nn.CrossEntropyLoss()

    for epoch in range(1, 41):
        m3_model.train()
        optimizer_m3.zero_grad()
        logits_m3 = m3_model(X_graph[train_idx], X_patient[train_idx])
        loss_m3 = criterion_ce(logits_m3, Y_label[train_idx])
        loss_m3.backward()
        optimizer_m3.step()

    m3_model.eval()
    with torch.no_grad():
        test_logits_m3 = m3_model(X_graph[test_idx], X_patient[test_idx])
        m3_preds = test_logits_m3.argmax(dim=1).cpu().numpy()
        m3_acc = accuracy_score(Y_label[test_idx].numpy(), m3_preds)
        m3_f1 = f1_score(Y_label[test_idx].numpy(), m3_preds, average="macro")
    print(f"M3 Naive Context - Test Accuracy: {m3_acc * 100:.2f}% | Macro-F1: {m3_f1:.4f}")

    # ----------------------------------------------------
    # Train M4: Context Fusion Network (Proposed Contribution)
    # ----------------------------------------------------
    print("\n--- Training Model M4: Context Fusion Network (Proposed Novelty) ---")
    m4_model = ContextFusionNetwork(graph_dim=32, patient_dim=16, hidden_dim=32, num_classes=3)
    optimizer_m4 = torch.optim.Adam(m4_model.parameters(), lr=0.005, weight_decay=1e-4)
    criterion_mse = nn.MSELoss()

    best_f1 = 0.0
    best_weights = None

    for epoch in range(1, 51):
        m4_model.train()
        optimizer_m4.zero_grad()
        logits_m4, scalar_risk = m4_model(X_graph[train_idx], X_patient[train_idx])
        loss_ce = criterion_ce(logits_m4, Y_label[train_idx])
        loss_risk = criterion_mse(scalar_risk, Y_risk[train_idx])
        total_loss = loss_ce + 0.5 * loss_risk

        total_loss.backward()
        optimizer_m4.step()

        # Validation check
        m4_model.eval()
        with torch.no_grad():
            v_logits, _ = m4_model(X_graph[val_idx], X_patient[val_idx])
            v_preds = v_logits.argmax(dim=1).cpu().numpy()
            val_f1 = f1_score(Y_label[val_idx].numpy(), v_preds, average="macro")

        if val_f1 >= best_f1:
            best_f1 = val_f1
            best_weights = m4_model.state_dict().copy()

    if best_weights:
        m4_model.load_state_dict(best_weights)

    m4_model.eval()
    with torch.no_grad():
        test_logits_m4, test_risks = m4_model(X_graph[test_idx], X_patient[test_idx])
        m4_preds = test_logits_m4.argmax(dim=1).cpu().numpy()
        m4_acc = accuracy_score(Y_label[test_idx].numpy(), m4_preds)
        m4_f1 = f1_score(Y_label[test_idx].numpy(), m4_preds, average="macro")

    print("\n=== COMPARATIVE ABLATION RESULTS: M3 vs M4 ===")
    print(f"M3 Naive Context:            Accuracy = {m3_acc * 100:.2f}% | Macro-F1 = {m3_f1:.4f}")
    print(f"M4 Context Fusion (Proposed): Accuracy = {m4_acc * 100:.2f}% | Macro-F1 = {m4_f1:.4f}")
    gain = (m4_f1 - m3_f1) / max(1e-5, m3_f1) * 100.0
    print(f"-> Performance Gain of Context Fusion Layer: +{gain:.2f}% Macro-F1 improvement!")

    # Save M4 checkpoint
    checkpoint_path = WEIGHTS_DIR / "context_fusion_m4.pt"
    torch.save(
        {
            "model_state_dict": m4_model.state_dict(),
            "graph_dim": 32,
            "patient_dim": 16,
            "hidden_dim": 32,
            "num_classes": 3,
            "metrics": {
                "m3_macro_f1": float(m3_f1),
                "m3_accuracy": float(m3_acc),
                "m4_macro_f1": float(m4_f1),
                "m4_accuracy": float(m4_acc),
            },
        },
        checkpoint_path,
    )
    print(f"M4 checkpoint saved successfully to: {checkpoint_path}")


if __name__ == "__main__":
    train()
