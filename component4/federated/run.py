import argparse
import subprocess
import sys
import time
from pathlib import Path

from config import NUM_CLINICS

# Folder that contains this file (component4/federated/). server.py and
# client.py live next to run.py, so this works from any working directory.
HERE = Path(__file__).resolve().parent
SERVER_SCRIPT = str(HERE / "server.py")
CLIENT_SCRIPT = str(HERE / "client.py")

# Examples:
#   python run.py 2.0                          -> FedAvg, ε=2.0, run 1
#   python run.py 0.5 --strategy fedprox --run 2
#   python run.py --no-dp --strategy fedprox      -> reference run without differential privacy
parser = argparse.ArgumentParser(description="Run one federated experiment")
parser.add_argument("epsilon", type=float, nargs="?", default=2.0, help="total privacy budget ε")
parser.add_argument("--strategy", choices=["fedavg", "fedprox"], default="fedavg")
parser.add_argument("--run", type=int, default=1, help="run number (sets the random seed)")
parser.add_argument("--no-dp", action="store_true", help="reference run without differential privacy")
args = parser.parse_args()
EPSILON = args.epsilon
LABEL = "no DP" if args.no_dp else f"ε={EPSILON}"
# Extra arguments passed to the server and every client
common = ["--run", str(args.run)] + (["--no-dp"] if args.no_dp else [])

print(f"=== AyurAI Federated Learning — {args.strategy}, {LABEL}, run {args.run} ===")
print("Starting server...")

server = subprocess.Popen(
    [sys.executable, SERVER_SCRIPT, str(EPSILON), "--strategy", args.strategy] + common
)
time.sleep(3)

print(f"Starting {NUM_CLINICS} clinic nodes...")
clients = [
    subprocess.Popen([sys.executable, CLIENT_SCRIPT, str(clinic_id), str(EPSILON)] + common)
    for clinic_id in range(1, NUM_CLINICS + 1)
]

# Wait for everything to finish; fail loudly if any process crashed
exit_codes = [server.wait()] + [client.wait() for client in clients]
if any(code != 0 for code in exit_codes):
    print(f"=== FAILED — exit codes {exit_codes} ===")
    sys.exit(1)

print(f"=== Complete — {args.strategy}, {LABEL}, run {args.run} ===")
