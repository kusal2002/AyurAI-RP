import flwr as fl
import torch
import torch.nn as nn
import numpy as np
from opacus import PrivacyEngine

# Simple anemia risk model
class AnemiaModel(nn.Module):
    def __init__(self):
        super(AnemiaModel, self).__init__()
        self.fc1 = nn.Linear(10, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 3)  # Low, Moderate, High risk

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)


class AyurAIClient(fl.client.NumPyClient):

    def __init__(self, clinic_id, epsilon=1.0):
        self.clinic_id = clinic_id
        self.epsilon = epsilon  # Privacy budget — controls how much noise is added
        self.model = AnemiaModel()
        self.optimizer = torch.optim.SGD(self.model.parameters(), lr=0.01)
        self.criterion = nn.CrossEntropyLoss()

        # TODO (Day 2): replace this RANDOM placeholder data with the real
        # anemia dataset, partitioned non-IID across clinics. The features
        # below are random noise, so any accuracy reported is meaningless.
        # Non-IID data per clinic
        np.random.seed(clinic_id)
        self.X = torch.tensor(np.random.rand(50, 10), dtype=torch.float32)

        if clinic_id == 1:
            # Clinic 1 — mostly severe anemia
            labels = [2]*35 + [1]*10 + [0]*5
        elif clinic_id == 2:
            # Clinic 2 — mostly mild cases
            labels = [0]*30 + [1]*15 + [2]*5
        else:
            # Clinic 3 — mixed
            labels = [0]*17 + [1]*17 + [2]*16

        self.y = torch.tensor(labels, dtype=torch.long)
        print(f"Clinic {self.clinic_id} ready — {labels.count(0)} Low, {labels.count(1)} Moderate, {labels.count(2)} High | ε={self.epsilon}")

        # Attach PrivacyEngine to add DP noise before weight transmission
        self.privacy_engine = PrivacyEngine()
        dataset = torch.utils.data.TensorDataset(self.X, self.y)
        self.loader = torch.utils.data.DataLoader(dataset, batch_size=16)

        self.model, self.optimizer, self.loader = self.privacy_engine.make_private_with_epsilon(
            module=self.model,
            optimizer=self.optimizer,
            data_loader=self.loader,
            epochs=5,
            target_epsilon=self.epsilon,
            target_delta=1e-5,
            max_grad_norm=1.0,
        )

    def get_parameters(self, config):
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        keys = list(self.model.state_dict().keys())
        state_dict = dict(zip(keys, [torch.tensor(p) for p in parameters]))
        self.model.load_state_dict(state_dict)

    def fit(self, parameters, config):
        self.set_parameters(parameters)
        self.model.train()
        for epoch in range(5):
            for X_batch, y_batch in self.loader:
                self.optimizer.zero_grad()
                output = self.model(X_batch)
                loss = self.criterion(output, y_batch)
                loss.backward()
                self.optimizer.step()

        # Check actual privacy spent
        epsilon_spent = self.privacy_engine.get_epsilon(delta=1e-5)
        print(f"Clinic {self.clinic_id} trained — Loss: {loss.item():.4f} | ε spent: {epsilon_spent:.4f}")
        return self.get_parameters(config={}), len(self.X), {"epsilon_spent": epsilon_spent}

    def evaluate(self, parameters, config):
        self.set_parameters(parameters)
        self.model.eval()
        with torch.no_grad():
            # TODO (Day 2): evaluate on a real held-out test split. These
            # inputs AND labels are random, so accuracy is ~chance (~0.33).
            X_eval = torch.tensor(np.random.rand(50, 10), dtype=torch.float32)
            y_eval = torch.tensor(np.random.randint(0, 3, 50), dtype=torch.long)
            output = self.model(X_eval)
            loss = self.criterion(output, y_eval).item()
            predicted = torch.argmax(output, dim=1)
            accuracy = (predicted == y_eval).float().mean().item()
        print(f"Clinic {self.clinic_id} eval — Loss: {loss:.4f} | Accuracy: {accuracy:.4f}")
        return loss, len(self.X), {"accuracy": accuracy}


if __name__ == "__main__":
    import sys
    clinic_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    epsilon = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    print(f"Starting AyurAI Client — Clinic {clinic_id} | Target ε={epsilon}")
    fl.client.start_client(
        server_address="127.0.0.1:8080",
        client=AyurAIClient(clinic_id, epsilon).to_client(),
    )