from pathlib import Path
import sys
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ml.dataset_builder import GraphDatasetBuilder
from app.ml.models.gat_link_predictor import GATLinkPredictor
from app.ml.models.kge_baselines import ComplExModel, RotatEModel
from app.ml.inference import GraphLinkPredictor
from app.models.patient_context import PatientContext, MedicationItem


def test_dataset_builder_shapes_and_splits():
    builder = GraphDatasetBuilder()
    herb_feats = builder.build_herb_features()
    drug_feats = builder.build_drug_features()
    pairs, labels = builder.build_interaction_dataset()

    assert herb_feats.shape[0] >= 30, "Expected at least 30 herbs in feature matrix"
    assert drug_feats.shape[0] >= 50, "Expected at least 50 drugs in feature matrix"
    assert len(pairs) >= 100, "Expected at least 100 interaction pairs"
    assert len(labels) == len(pairs)

    splits = builder.get_splits()
    assert len(splits["train_pairs"]) > 0
    assert len(splits["val_pairs"]) > 0
    assert len(splits["test_pairs"]) > 0


def test_gat_model_forward_and_probabilities():
    builder = GraphDatasetBuilder()
    herb_feats = builder.build_herb_features()
    drug_feats = builder.build_drug_features()

    model = GATLinkPredictor(
        herb_in_dim=herb_feats.shape[1],
        drug_in_dim=drug_feats.shape[1],
        hidden_dim=32,
        out_dim=16,
    )

    h_idx = torch.tensor([0, 1, 2], dtype=torch.long)
    d_idx = torch.tensor([0, 1, 2], dtype=torch.long)

    logits = model(herb_feats, drug_feats, h_idx, d_idx)
    assert logits.shape == (3,), f"Expected shape (3,), got {logits.shape}"
    assert not torch.isnan(logits).any(), "Found NaN in logits"

    prob = model.predict_probability(herb_feats, drug_feats, 0, 0)
    assert 0.0 <= prob <= 1.0, f"Probability out of range: {prob}"


def test_kge_baselines_forward():
    num_entities = 100
    complex_model = ComplExModel(num_entities=num_entities, embedding_dim=32)
    rotate_model = RotatEModel(num_entities=num_entities, embedding_dim=32)

    h = torch.tensor([0, 1, 2], dtype=torch.long)
    r = torch.tensor([0, 0, 1], dtype=torch.long)
    t = torch.tensor([5, 6, 7], dtype=torch.long)

    c_scores = complex_model(h, r, t)
    assert c_scores.shape == (3,)

    r_scores = rotate_model(h, r, t)
    assert r_scores.shape == (3,)


def test_graph_link_predictor_real_inference():
    predictor = GraphLinkPredictor()
    assert predictor.model is not None, "GAT model weights were not loaded"

    patient = PatientContext(
        patient_id="PT-GNN-TEST",
        age=52,
        gender="Male",
        current_medications=[
            MedicationItem(name="Losartan", drug_class="ARB"),
            MedicationItem(name="Atorvastatin", drug_class="Statin"),
        ],
    )

    findings = predictor.predict_interactions("Ashwagandha", patient, threshold=0.40)
    assert len(findings) >= 1
    assert any("Losartan" in f.target_drug or "Atorvastatin" in f.target_drug for f in findings)
    first = findings[0]
    assert 0.0 <= first.prediction_confidence <= 1.0
    assert first.interaction_type == "In-Silico Predicted (GAT)"
