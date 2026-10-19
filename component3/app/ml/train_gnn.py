"""Training Pipeline for GAT Link Prediction Model (M2 Baseline).

Trains the Graph Attention Network on the Safety Knowledge Graph interaction pairs,
evaluates on validation/test splits, and exports the checkpoint weights.
"""

from pathlib import Path
import sys
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.dataset_builder import GraphDatasetBuilder
from app.ml.models.gat_link_predictor import GATLinkPredictor


def compute_metrics(y_true, y_scores):
    """Computes ROC-AUC, PR-AUC, and Accuracy."""
    y_true_np = y_true.detach().cpu().numpy()
    y_scores_np = y_scores.detach().cpu().numpy()
    y_pred_np = (y_scores_np >= 0.5).astype(float)

    acc = (y_true_np == y_pred_np).mean()
    try:
        roc = roc_auc_score(y_true_np, y_scores_np)
    except Exception:
        roc = 0.5

    try:
        precision, recall, _ = precision_recall_curve(y_true_np, y_scores_np)
        pr_auc = auc(recall, precision)
    except Exception:
        pr_auc = 0.5

    return {"accuracy": float(acc), "roc_auc": float(roc), "pr_auc": float(pr_auc)}


def train():
    torch.manual_seed(42)
    builder = GraphDatasetBuilder()
    splits = builder.get_splits(test_ratio=0.20, val_ratio=0.15, seed=42)

    herb_feats = splits["herb_features"]
    drug_feats = splits["drug_features"]

    train_pairs = splits["train_pairs"]
    train_labels = splits["train_labels"]
    val_pairs = splits["val_pairs"]
    val_labels = splits["val_labels"]
    test_pairs = splits["test_pairs"]
    test_labels = splits["test_labels"]

    print("=== AyurAI GNN Training Pipeline (M2 Baseline) ===")
    print(f"Herb Feature Dim: {herb_feats.shape[1]}, Drug Feature Dim: {drug_feats.shape[1]}")
    print(f"Dataset Splits: Train={len(train_pairs)}, Val={len(val_pairs)}, Test={len(test_pairs)}")

    model = GATLinkPredictor(
        herb_in_dim=herb_feats.shape[1],
        drug_in_dim=drug_feats.shape[1],
        hidden_dim=64,
        out_dim=32,
        dropout=0.2,
    )

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=1e-4)

    best_val_auc = 0.0
    best_weights = None

    for epoch in range(1, 61):
        model.train()
        optimizer.zero_grad()

        h_idx = train_pairs[:, 0]
        d_idx = train_pairs[:, 1]
        logits = model(herb_feats, drug_feats, h_idx, d_idx)
        loss = criterion(logits, train_labels)

        loss.backward()
        optimizer.step()

        # Validation
        model.eval()
        with torch.no_grad():
            v_h_idx = val_pairs[:, 0]
            v_d_idx = val_pairs[:, 1]
            val_logits = model(herb_feats, drug_feats, v_h_idx, v_d_idx)
            val_loss = criterion(val_logits, val_labels)
            val_probs = torch.sigmoid(val_logits)
            val_metrics = compute_metrics(val_labels, val_probs)

        if val_metrics["pr_auc"] >= best_val_auc:
            best_val_auc = val_metrics["pr_auc"]
            best_weights = model.state_dict().copy()

        if epoch % 10 == 0 or epoch == 1:
            print(
                f"Epoch {epoch:02d}/60 | Train Loss: {loss.item():.4f} | "
                f"Val Loss: {val_loss.item():.4f} | Val ROC-AUC: {val_metrics['roc_auc']:.4f} | "
                f"Val PR-AUC: {val_metrics['pr_auc']:.4f}"
            )

    # Load best weights & evaluate on held-out test split
    if best_weights:
        model.load_state_dict(best_weights)

    model.eval()
    with torch.no_grad():
        t_h_idx = test_pairs[:, 0]
        t_d_idx = test_pairs[:, 1]
        test_logits = model(herb_feats, drug_feats, t_h_idx, t_d_idx)
        test_probs = torch.sigmoid(test_logits)
        test_metrics = compute_metrics(test_labels, test_probs)

    print("\n=== Final Held-Out Test Evaluation ===")
    print(f"Test Accuracy: {test_metrics['accuracy'] * 100:.2f}%")
    print(f"Test ROC-AUC:  {test_metrics['roc_auc']:.4f}")
    print(f"Test PR-AUC:   {test_metrics['pr_auc']:.4f} (Primary In-Silico Metric)")

    # Save weights checkpoint
    weights_dir = BASE_DIR / "app" / "ml" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = weights_dir / "gat_safety_v1.pt"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "herb_in_dim": herb_feats.shape[1],
            "drug_in_dim": drug_feats.shape[1],
            "herb_to_idx": splits["herb_to_idx"],
            "drug_to_idx": splits["drug_to_idx"],
            "idx_to_herb": splits["idx_to_herb"],
            "idx_to_drug": splits["idx_to_drug"],
            "test_metrics": test_metrics,
        },
        checkpoint_path,
    )
    print(f"Model checkpoint saved successfully to: {checkpoint_path}")


if __name__ == "__main__":
    train()
