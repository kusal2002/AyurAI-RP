"""Shared experiment settings for the server and the clinic clients.

Keeping them in one file guarantees the server and every client use the
same values (for example, the number of rounds the privacy budget is
spread over).
"""

import os
from pathlib import Path

# Read component4/.env if python-dotenv is available (it is in the venv).
# Only C4_DATA_DIR is used from it here.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# Where clients find the server. Local runs use the default; in Docker,
# docker-compose.yml sets SERVER_ADDRESS=server:8080 (the server container).
SERVER_ADDRESS = os.getenv("SERVER_ADDRESS", "127.0.0.1:8080")
# Simulated clinic nodes (proposal SO1: 3). Set C4_NUM_CLINICS=10 to run the
# scalability test (NFR: at least 10 nodes without architectural changes).
NUM_CLINICS = int(os.getenv("C4_NUM_CLINICS", "3"))
NUM_ROUNDS = 10          # federated rounds per run
LOCAL_EPOCHS = 5         # local training epochs per round
BATCH_SIZE = 16
# 0.1 (was 0.01): with 0.01 the model never left "always predict Low" on the real
# CP-AnemiC features. Chosen on pooled results (no separate validation set yet).
LEARNING_RATE = 0.1

# Differential privacy (proposal SO2)
DELTA = 1e-5             # δ, fixed for every experiment
MAX_GRAD_NORM = 1.0      # per-sample gradient clipping bound C
EPSILONS = [0.1, 0.5, 1.0, 2.0, 5.0]

# FedProx proximal coefficient μ (proposal: μ = 0.1, Li et al. [2])
PROXIMAL_MU = 0.1

TEST_FRACTION = 0.2      # share of each clinic's data held out for evaluation

# ---------- Real data: CP-AnemiC v2 (from Component 1) ----------
# Datasets live OUTSIDE the repo (patient images): C4_DATA_DIR in component4/.env.
# prepare_data.py turns the images into colour features and saves them here;
# if this file is missing, data.py falls back to placeholder data.
DATA_DIR = Path(os.getenv("C4_DATA_DIR", "")) if os.getenv("C4_DATA_DIR") else None
FEATURES_FILE = DATA_DIR / "processed" / "cpanemic_features.csv" if DATA_DIR else None

# Risk tiers from lab haemoglobin (g/dL), based on WHO anaemia severity bands:
#   High risk: Hb < 8.0 (severe) | Moderate: 8.0-10.9 | Low: Hb >= 11.0
# The dataset itself labels Hb >= 11.0 as non-anaemic. To be confirmed with Component 1.
HB_HIGH_RISK_BELOW = 8.0
HB_LOW_RISK_FROM = 11.0
TIER_NAMES = ("Low", "Moderate", "High")   # class 0, 1, 2

# Simulated clinics with a non-IID split (proposal section 3.2):
# estate-sector clinic -> more severe cases; urban peripheral -> mostly mild.
#  - label_counts: (Low, Moderate, High) rows for the PLACEHOLDER data
#  - tier_shares:  share of each tier's real patients sent to this clinic
#                  (Low, Moderate, High); each tier's shares sum to 1 across clinics
CLINIC_PROFILES = {
    1: {"name": "Estate-sector clinic", "label_counts": (5, 10, 35), "tier_shares": (0.15, 0.45, 0.60)},
    2: {"name": "Urban peripheral clinic", "label_counts": (30, 15, 5), "tier_shares": (0.50, 0.15, 0.10)},
    3: {"name": "Mixed rural clinic", "label_counts": (17, 17, 16), "tier_shares": (0.35, 0.40, 0.30)},
}

# Scalability test: any clinic count other than the 3 profiles above. Patients are
# then spread evenly over the clinics by patient id (no severity skew), and result
# files get an "n<clinics>_" prefix so they never overwrite the main results.
SCALE_TEST = NUM_CLINICS != len(CLINIC_PROFILES)
