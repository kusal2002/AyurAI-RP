import argparse

import flwr as fl
import torch
import torch.nn as nn
from opacus import PrivacyEngine
from torch.utils.data import DataLoader

from config import (
    BATCH_SIZE,
    DELTA,
    LEARNING_RATE,
    LOCAL_EPOCHS,
    MAX_GRAD_NORM,
    NUM_ROUNDS,
    SERVER_ADDRESS,
)
from data import load_clinic_data
from model import AnemiaModel


class AyurAIClient(fl.client.NumPyClient):

    def __init__(self, clinic_id, epsilon, run_id):
        self.clinic_id = clinic_id
        self.epsilon = epsilon  # total privacy budget for the WHOLE federated run

        # Different seed per run and clinic, so repeated runs give
        # independent DP noise (results are averaged over runs).
        torch.manual_seed(run_id * 100 + clinic_id)

        self.model = AnemiaModel()
        self.optimizer = torch.optim.SGD(self.model.parameters(), lr=LEARNING_RATE)
        self.criterion = nn.CrossEntropyLoss()

        train_set, test_set = load_clinic_data(clinic_id)
        self.num_train = len(train_set)
        self.train_loader = DataLoader(train_set, batch_size=BATCH_SIZE)
        self.test_loader = DataLoader(test_set, batch_size=BATCH_SIZE)
        print(f"Clinic {clinic_id} ready — {self.num_train} train / {len(test_set)} test rows | target ε={epsilon}")

        # Attach Opacus: clips each sample's gradient and adds Gaussian noise.
        # The noise is calibrated for ALL the training this client will do
        # (LOCAL_EPOCHS per round x NUM_ROUNDS rounds), so the total ε spent
        # at the end of the run stays within the target ε.
        self.privacy_engine = PrivacyEngine()
        self.model, self.optimizer, self.train_loader = self.privacy_engine.make_private_with_epsilon(
            module=self.model,
            optimizer=self.optimizer,
            data_loader=self.train_loader,
            epochs=LOCAL_EPOCHS * NUM_ROUNDS,
            target_epsilon=self.epsilon,
            target_delta=DELTA,
            max_grad_norm=MAX_GRAD_NORM,
        )

    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        keys = list(self.model.state_dict().keys())
        state_dict = dict(zip(keys, [torch.tensor(p) for p in parameters]))
        self.model.load_state_dict(state_dict)

    def fit(self, parameters, config):
        self.set_parameters(parameters)

        # FedProx sends μ in the config; FedAvg sends nothing, so μ = 0
        # and the proximal step below is skipped.
        mu = float(config.get("proximal_mu", 0.0))
        global_params = [p.detach().clone() for p in self.model.parameters()]

        self.model.train()
        for epoch in range(LOCAL_EPOCHS):
            total_loss, batches = 0.0, 0
            for X_batch, y_batch in self.train_loader:
                if len(y_batch) == 0:  # Poisson sampling can produce an empty batch
                    continue
                self.optimizer.zero_grad()
                loss = self.criterion(self.model(X_batch), y_batch)
                loss.backward()
                self.optimizer.step()  # DP step: clip + noise + update

                # FedProx proximal step: pull the weights back towards the
                # global model by lr * μ * (w - w_global). This equals one
                # gradient step on (μ/2)·||w - w_global||². It is done
                # outside Opacus because the term uses no patient data
                # (Opacus would silently ignore it inside the loss).
                if mu > 0:
                    with torch.no_grad():
                        for p, g in zip(self.model.parameters(), global_params):
                            p -= LEARNING_RATE * mu * (p - g)

                total_loss += loss.item()
                batches += 1

        avg_loss = total_loss / max(batches, 1)
        epsilon_spent = self.privacy_engine.get_epsilon(delta=DELTA)
        print(f"Clinic {self.clinic_id} trained — loss {avg_loss:.4f} | μ={mu} | ε spent so far {epsilon_spent:.4f}")
        return self.get_parameters(config={}), self.num_train, {"epsilon_spent": epsilon_spent}

    def evaluate(self, parameters, config):
        # Evaluate the global model on this clinic's held-out test rows.
        # TODO (data): meaningful only once real data replaces the placeholder.
        self.set_parameters(parameters)
        self.model.eval()
        total_loss, correct, count = 0.0, 0, 0
        with torch.no_grad():
            for X_batch, y_batch in self.test_loader:
                output = self.model(X_batch)
                total_loss += self.criterion(output, y_batch).item() * len(y_batch)
                correct += (output.argmax(dim=1) == y_batch).sum().item()
                count += len(y_batch)
        loss, accuracy = total_loss / count, correct / count
        print(f"Clinic {self.clinic_id} eval — loss {loss:.4f} | accuracy {accuracy:.4f}")
        return loss, count, {"accuracy": accuracy}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AyurAI clinic node")
    parser.add_argument("clinic_id", type=int)
    parser.add_argument("epsilon", type=float)
    parser.add_argument("--run", type=int, default=1, help="run number (sets the random seed)")
    args = parser.parse_args()

    print(f"Starting AyurAI Client — Clinic {args.clinic_id} | target ε={args.epsilon} | run {args.run}")
    fl.client.start_client(
        server_address=SERVER_ADDRESS,
        client=AyurAIClient(args.clinic_id, args.epsilon, args.run).to_client(),
    )
