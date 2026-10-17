import subprocess
import time
import sys
from pathlib import Path

# Folder that contains this file (component4/federated/). server.py and
# client.py live next to run.py, so this works from any working directory.
HERE = Path(__file__).resolve().parent
SERVER_SCRIPT = str(HERE / "server.py")
CLIENT_SCRIPT = str(HERE / "client.py")

# Privacy budget from the command line, e.g. `python run.py 0.5`
# Try different values: 0.1, 0.5, 1.0, 2.0, 5.0 (default 2.0)
EPSILON = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0

print(f"=== AyurAI Federated Learning — ε={EPSILON} ===")
print("Starting server...")

# The server gets epsilon only so it can name the results CSV
server = subprocess.Popen([sys.executable, SERVER_SCRIPT, str(EPSILON)])
time.sleep(3)

print("Starting 3 clinic nodes...")
client1 = subprocess.Popen([sys.executable, CLIENT_SCRIPT, "1", str(EPSILON)])
client2 = subprocess.Popen([sys.executable, CLIENT_SCRIPT, "2", str(EPSILON)])
client3 = subprocess.Popen([sys.executable, CLIENT_SCRIPT, "3", str(EPSILON)])

server.wait()
client1.wait()
client2.wait()
client3.wait()

print(f"=== Complete — ε={EPSILON} ===")
