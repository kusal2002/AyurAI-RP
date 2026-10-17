import csv
import sys
from pathlib import Path

import flwr as fl
from flwr.server.strategy import FedAvg

# Folder where per-round metrics are saved: component4/results/
# (this file lives in component4/federated/, so go up one level)
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def weighted_average(metrics):
    """Combine the clients' evaluation accuracies into one number.

    `metrics` is a list of (num_examples, {"accuracy": value}) pairs,
    one per client. Clients with more examples count proportionally more.
    """
    total_examples = sum(num_examples for num_examples, _ in metrics)
    weighted_sum = sum(num_examples * m["accuracy"] for num_examples, m in metrics)
    return {"accuracy": weighted_sum / total_examples}


# Simple federated server for AyurAI anemia screening (FedAvg = baseline)
strategy = FedAvg(
    min_fit_clients=3,       # minimum 3 clinic nodes to train
    min_evaluate_clients=3,  # minimum 3 clinic nodes to evaluate
    min_available_clients=3, # wait until 3 clinics are connected
    evaluate_metrics_aggregation_fn=weighted_average,  # aggregate client accuracy
)


def save_history_to_csv(history, epsilon):
    """Write round, aggregated loss and aggregated accuracy to a CSV file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / f"fedavg_eps{epsilon}.csv"

    # history.losses_distributed      -> [(round, loss), ...]
    # history.metrics_distributed     -> {"accuracy": [(round, acc), ...]}
    accuracy_by_round = dict(history.metrics_distributed.get("accuracy", []))

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "loss", "accuracy"])
        for round_num, loss in history.losses_distributed:
            writer.writerow([round_num, loss, accuracy_by_round.get(round_num, "")])

    print(f"Saved per-round metrics to {csv_path}")


if __name__ == "__main__":
    # Epsilon is passed in by run.py; it is only used to name the CSV file
    epsilon = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    print("Starting AyurAI Federated Server...")
    history = fl.server.start_server(
        server_address="0.0.0.0:8080",
        config=fl.server.ServerConfig(num_rounds=3),
        strategy=strategy,
    )
    save_history_to_csv(history, epsilon)
