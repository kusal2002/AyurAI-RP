"""Per-clinic data loading with a non-IID split.

TODO (data): replace the PLACEHOLDER data below with the CP-AnemiC dataset
used by Component 1 (request the files from the C1 owner). The features
here are random noise, so any accuracy measured on them is meaningless.
Only the label distribution per clinic is realistic.
"""

import numpy as np
import torch
from torch.utils.data import TensorDataset

from config import CLINIC_PROFILES, TEST_FRACTION

DATA_SOURCE = "PLACEHOLDER (random features, not real patient data)"


def load_clinic_data(clinic_id, num_features=10):
    """Return (train_dataset, test_dataset) for one clinic."""
    # Fixed seed per clinic: the data is the same in every run,
    # only the training randomness changes between runs.
    rng = np.random.default_rng(clinic_id)

    low, moderate, high = CLINIC_PROFILES[clinic_id]["label_counts"]
    labels = np.array([0] * low + [1] * moderate + [2] * high)
    features = rng.random((len(labels), num_features))  # PLACEHOLDER noise

    # Shuffle, then hold out TEST_FRACTION of the rows for evaluation
    order = rng.permutation(len(labels))
    features, labels = features[order], labels[order]
    n_test = int(len(labels) * TEST_FRACTION)

    X = torch.tensor(features, dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.long)
    test_set = TensorDataset(X[:n_test], y[:n_test])
    train_set = TensorDataset(X[n_test:], y[n_test:])
    return train_set, test_set
