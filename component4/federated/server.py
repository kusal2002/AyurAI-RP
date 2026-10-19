import argparse
import csv
import os
from pathlib import Path

import flwr as fl
from flwr.server.strategy import FedAvg, FedProx

from config import NUM_CLINICS, NUM_ROUNDS, PROXIMAL_MU

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


def max_epsilon(metrics):
    """Report the largest ε spent by any clinic (the worst-case privacy cost)."""
    return {"epsilon_spent": max(m["epsilon_spent"] for _, m in metrics)}


def build_strategy(name):
    """FedAvg = baseline; FedProx = proposed aggregation (μ from config.py)."""
    common = dict(
        min_fit_clients=NUM_CLINICS,       # every clinic trains each round
        min_evaluate_clients=NUM_CLINICS,  # every clinic evaluates each round
        min_available_clients=NUM_CLINICS, # wait until all clinics are connected
        evaluate_metrics_aggregation_fn=weighted_average,
        fit_metrics_aggregation_fn=max_epsilon,
    )
    if name == "fedprox":
        return FedProx(proximal_mu=PROXIMAL_MU, **common)
    return FedAvg(**common)


def save_history_to_csv(history, strategy, epsilon, run):
    """Write round, aggregated loss, accuracy and ε spent to a CSV file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / f"{strategy}_eps{epsilon}_run{run}.csv"

    # history.losses_distributed          -> [(round, loss), ...]
    # history.metrics_distributed         -> {"accuracy": [(round, acc), ...]}
    # history.metrics_distributed_fit     -> {"epsilon_spent": [(round, eps), ...]}
    accuracy_by_round = dict(history.metrics_distributed.get("accuracy", []))
    epsilon_by_round = dict(history.metrics_distributed_fit.get("epsilon_spent", []))

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "loss", "accuracy", "epsilon_spent"])
        for round_num, loss in history.losses_distributed:
            writer.writerow([
                round_num,
                loss,
                accuracy_by_round.get(round_num, ""),
                epsilon_by_round.get(round_num, ""),
            ])

    print(f"Saved per-round metrics to {csv_path}")


if __name__ == "__main__":
    # These arguments come from run.py; epsilon and run only name the CSV.
    # Epsilon priority: explicit argument > EPSILON environment variable
    # (set by docker-compose.yml) > 2.0.
    parser = argparse.ArgumentParser(description="AyurAI federated server")
    parser.add_argument("epsilon", type=float, nargs="?", default=float(os.getenv("EPSILON", "2.0")))
    parser.add_argument("--strategy", choices=["fedavg", "fedprox"], default="fedavg")
    parser.add_argument("--run", type=int, default=1)
    args = parser.parse_args()

    print(f"Starting AyurAI Federated Server — {args.strategy}, {NUM_ROUNDS} rounds")
    history = fl.server.start_server(
        server_address="0.0.0.0:8080",
        config=fl.server.ServerConfig(num_rounds=NUM_ROUNDS),
        strategy=build_strategy(args.strategy),
    )
    save_history_to_csv(history, args.strategy, args.epsilon, args.run)
