# Component 4 — Privacy-Preserving Federated Learning for Anemia Risk Screening

This component builds a federated learning framework where several clinics
train a shared anemia risk model (Low / Moderate / High) without sending raw
patient data to a central server. Training is coordinated with
[Flower](https://flower.ai/), and each clinic applies differential privacy
to its updates with [Opacus](https://opacus.ai/), controlled by a privacy
budget ε (epsilon). The current baseline uses FedAvg aggregation. Later
phases will add FedProx for non-IID data, a FAKL knowledge layer on Neo4j,
and a secured FastAPI/JWT/PostgreSQL service layer.

## Folder structure

```
component4/
├── federated/        # Flower server, clients and launcher
│   ├── server.py     # FedAvg server; writes per-round metrics CSV
│   ├── client.py     # Clinic client with Opacus differential privacy
│   └── run.py        # Starts 1 server + 3 clients for a given ε
├── privacy/          # (planned) privacy accounting / DP utilities
├── fakl/             # (planned) FAKL knowledge layer on Neo4j
├── security/         # (planned) FastAPI + JWT + PostgreSQL
├── data/             # datasets (data/raw/ is git-ignored)
├── results/          # experiment outputs, e.g. fedavg_eps2.0.csv
├── docs/             # research logbook and notes
├── README.md
├── requirements.txt
└── .gitignore
```

## Setup (Windows)

Run these from the repository root in PowerShell:

```powershell
# 1. Create a virtual environment
python -m venv component4\venv

# 2. Activate it
component4\venv\Scripts\Activate.ps1
# (if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned)

# 3. Install pinned dependencies
pip install -r component4\requirements.txt
```

## Running

```powershell
python component4/federated/run.py 2.0
```

The argument is the privacy budget ε (default `2.0`). This starts the server
and 3 clinic clients on `127.0.0.1:8080`, runs 3 federated rounds, and
writes per-round metrics to `component4/results/fedavg_eps2.0.csv` with the
columns `round, loss, accuracy`.

## Status

**Done (Day 1)**
- Project folder structure created
- FedAvg baseline server and Opacus DP clients moved into `federated/`
- `run.py` works from any working directory and takes ε from the command line
- Server aggregates client accuracy (weighted average) and logs per-round
  loss/accuracy to `results/`

**Placeholder / known limitations**
- Clients train and evaluate on **randomly generated data**, so the reported
  accuracy (~0.33, i.e. chance level) has no meaning yet.

**Next (Day 2)**
- Load a real anemia dataset
- Non-IID partitioning across clinics
- FedProx strategy for comparison against the FedAvg baseline
