"""Shared experiment settings for the server and the clinic clients.

Keeping them in one file guarantees the server and every client use the
same values (for example, the number of rounds the privacy budget is
spread over).
"""

import os

# Where clients find the server. Local runs use the default; in Docker,
# docker-compose.yml sets SERVER_ADDRESS=server:8080 (the server container).
SERVER_ADDRESS = os.getenv("SERVER_ADDRESS", "127.0.0.1:8080")
NUM_CLINICS = 3          # simulated clinic nodes (proposal SO1)
NUM_ROUNDS = 10          # federated rounds per run
LOCAL_EPOCHS = 5         # local training epochs per round
BATCH_SIZE = 16
LEARNING_RATE = 0.01

# Differential privacy (proposal SO2)
DELTA = 1e-5             # δ, fixed for every experiment
MAX_GRAD_NORM = 1.0      # per-sample gradient clipping bound C
EPSILONS = [0.1, 0.5, 1.0, 2.0, 5.0]

# FedProx proximal coefficient μ (proposal: μ = 0.1, Li et al. [2])
PROXIMAL_MU = 0.1

TEST_FRACTION = 0.2      # share of each clinic's data held out for evaluation

# Simulated clinics with a non-IID label skew: (Low, Moderate, High) counts.
# Estate-sector clinic -> mostly severe; urban peripheral -> mostly mild
# (proposal section 3.2). Read by data.py and shown on the dashboard.
CLINIC_PROFILES = {
    1: {"name": "Estate-sector clinic", "label_counts": (5, 10, 35)},
    2: {"name": "Urban peripheral clinic", "label_counts": (30, 15, 5)},
    3: {"name": "Mixed rural clinic", "label_counts": (17, 17, 16)},
}
