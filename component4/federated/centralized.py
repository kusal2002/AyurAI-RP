"""Baselines for the federated results (proposal section 3.3).

1. Majority class: always predict the most common tier. Any useful model must beat this.
2. Centralised training: pool every clinic's training data on one machine (no
   federation, no differential privacy) and train the same model for the same
   number of epochs. This is the "upper bound" federated learning is compared with,
   even though pooling patient data is exactly what the proposal avoids.

Usage:  python component4/federated/centralized.py [--runs 3]
Writes  component4/results/centralized.csv
"""

import argparse
import csv
import statistics
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import ConcatDataset, DataLoader

from config import BATCH_SIZE, LEARNING_RATE, LOCAL_EPOCHS, NUM_CLINICS, NUM_ROUNDS
from data import DATA_SOURCE, load_clinic_data
from model import AnemiaModel

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def macro_f1(true, pred, num_classes=3):
    """Average F1 over the classes, so the rare High tier counts as much as Low."""
    scores = []
    for c in range(num_classes):
        tp = sum(1 for t, p in zip(true, pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(true, pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(true, pred) if t == c and p != c)
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(scores) / num_classes


def run_once(seed, train_set, test_set):
    torch.manual_seed(seed)
    model = AnemiaModel()
    optimizer = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()
    loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True)

    # Same total amount of training as one federated run: LOCAL_EPOCHS x NUM_ROUNDS
    for _ in range(LOCAL_EPOCHS * NUM_ROUNDS):
        for X, y in loader:
            optimizer.zero_grad()
            criterion(model(X), y).backward()
            optimizer.step()

    X_test = torch.stack([x for x, _ in test_set])
    y_test = [int(y) for _, y in test_set]
    with torch.no_grad():
        pred = model(X_test).argmax(dim=1).tolist()
    accuracy = sum(p == t for p, t in zip(pred, y_test)) / len(y_test)
    return accuracy, macro_f1(y_test, pred)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    # Pool the SAME train/test splits the clinics use in federated training
    splits = [load_clinic_data(c) for c in range(1, NUM_CLINICS + 1)]
    train_set = ConcatDataset([train for train, _ in splits])
    test_set = ConcatDataset([test for _, test in splits])

    test_labels = [int(y) for _, y in test_set]
    majority = max(set(test_labels), key=test_labels.count)
    majority_acc = test_labels.count(majority) / len(test_labels)
    majority_f1 = macro_f1(test_labels, [majority] * len(test_labels))

    results = [run_once(seed, train_set, test_set) for seed in range(1, args.runs + 1)]
    accs, f1s = [r[0] for r in results], [r[1] for r in results]

    rows = [
        {"method": "majority_class", "accuracy_mean": majority_acc, "accuracy_std": 0.0,
         "macro_f1_mean": majority_f1, "runs": 1},
        {"method": "centralised_no_dp", "accuracy_mean": statistics.mean(accs),
         "accuracy_std": statistics.stdev(accs) if len(accs) > 1 else 0.0,
         "macro_f1_mean": statistics.mean(f1s), "runs": args.runs},
    ]
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / "centralized.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) + ["train_rows", "test_rows", "data_source"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "train_rows": len(train_set), "test_rows": len(test_set), "data_source": DATA_SOURCE})

    print(f"Data: {DATA_SOURCE} | train {len(train_set)} | test {len(test_set)}")
    for row in rows:
        print(f"{row['method']:18s} accuracy {row['accuracy_mean']:.3f} ± {row['accuracy_std']:.3f} | macro-F1 {row['macro_f1_mean']:.3f}")
