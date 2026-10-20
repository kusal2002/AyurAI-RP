"""Per-clinic data with a non-IID split.

REAL data: CP-AnemiC v2 (Component 1's dataset): conjunctiva photos turned into
10 colour features by prepare_data.py, labelled with risk tiers from lab Hb.
Used automatically when the features file exists (C4_DATA_DIR in component4/.env).

PLACEHOLDER data: random features with realistic label counts per clinic. Used
when the real features file is missing (e.g. a teammate without the dataset,
or the Docker containers). Accuracy on placeholder data is meaningless.
"""

import csv

import numpy as np
import torch
from torch.utils.data import TensorDataset

from config import CLINIC_PROFILES, FEATURES_FILE, TEST_FRACTION
from features import FEATURE_NAMES

USE_REAL_DATA = FEATURES_FILE is not None and FEATURES_FILE.exists()
DATA_SOURCE = (
    "CP-AnemiC v2 (conjunctiva colour features, lab-Hb risk tiers)"
    if USE_REAL_DATA
    else "PLACEHOLDER (random features, not real patient data)"
)


def _real_clinic_rows(clinic_id):
    """Features and tier labels of the patients assigned to this clinic."""
    with open(FEATURES_FILE, newline="") as f:
        rows = [row for row in csv.DictReader(f) if int(row["clinic_id"]) == clinic_id]
    features = np.array([[float(row[name]) for name in FEATURE_NAMES] for row in rows])
    labels = np.array([int(row["tier"]) for row in rows])
    return features, labels


def _placeholder_clinic_rows(clinic_id, rng, num_features=10):
    low, moderate, high = CLINIC_PROFILES[clinic_id]["label_counts"]
    labels = np.array([0] * low + [1] * moderate + [2] * high)
    return rng.random((len(labels), num_features)), labels   # random noise features


def _split_clinic(clinic_id):
    """Shuffle one clinic's rows with a fixed seed and split them into train / test arrays."""
    # Fixed seed per clinic: the split is the same in every run;
    # only the training randomness (and DP noise) changes between runs.
    rng = np.random.default_rng(clinic_id)
    if USE_REAL_DATA:
        features, labels = _real_clinic_rows(clinic_id)
    else:
        features, labels = _placeholder_clinic_rows(clinic_id, rng)

    order = rng.permutation(len(labels))
    features, labels = features[order], labels[order]
    n_test = int(len(labels) * TEST_FRACTION)          # held out for evaluation
    return features[n_test:], labels[n_test:], features[:n_test], labels[:n_test]


def _federated_scaling():
    """Global mean / standard deviation of each feature over all clinics' TRAINING rows.

    Computed only from each clinic's per-feature count, sum and sum of squares
    (20 numbers per clinic, no patient records): what a federated statistics step
    would share. Prototype limitation: these aggregates are not DP-protected.
    """
    count, total, total_sq = 0, 0.0, 0.0
    for clinic_id in CLINIC_PROFILES:
        train_x, _, _, _ = _split_clinic(clinic_id)
        count += len(train_x)
        total = total + train_x.sum(axis=0)
        total_sq = total_sq + (train_x ** 2).sum(axis=0)
    mean = total / count
    std = np.sqrt(np.maximum(total_sq / count - mean ** 2, 1e-12))
    return mean, std


def load_clinic_data(clinic_id):
    """Return (train_dataset, test_dataset) for one clinic."""
    train_x, train_y, test_x, test_y = _split_clinic(clinic_id)

    if USE_REAL_DATA:
        # Put every feature on the same scale (mean 0, spread 1), using the shared
        # statistics, so all clinics transform their data identically.
        mean, std = _federated_scaling()
        train_x, test_x = (train_x - mean) / std, (test_x - mean) / std

    def to_dataset(x, y):
        return TensorDataset(torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.long))

    return to_dataset(train_x, train_y), to_dataset(test_x, test_y)
