# Component 4 — Privacy-Preserving Federated Learning, Security & Governance

This component lets several clinics jointly train the AyurAI anemia risk model
(Low / Moderate / High) without any clinic sharing raw patient data. Training is
coordinated with [Flower](https://flower.ai/) using FedProx (proposed) and FedAvg
(baseline), and every clinic applies differential privacy with
[Opacus](https://opacus.ai/) before its model update leaves the node. A FastAPI
service adds the security and governance layer: JWT sign-in, role-based access
control, practitioner decisions and a tamper-evident (hash-chained) audit log whose
head hash is anchored on the Ethereum Sepolia test network. A later phase adds FAKL
(federated Neo4j knowledge-graph weights).

## Folder structure

```
component4/
├── federated/          # Flower + Opacus experiments
│   ├── config.py       # shared settings: rounds, μ, δ, ε values, clinic profiles
│   ├── features.py     # conjunctiva photo -> 10 colour (pallor) features
│   ├── prepare_data.py # CP-AnemiC images + lab Hb -> features CSV, clinic per patient
│   ├── data.py         # per-clinic non-IID data (real CP-AnemiC, or placeholder fallback)
│   ├── model.py        # anemia risk classifier
│   ├── client.py       # clinic node: DP training + FedProx proximal step
│   ├── server.py       # FedAvg / FedProx server; writes per-round CSV
│   ├── run.py          # one experiment: server + 3 clinics (--no-dp for a reference run)
│   ├── centralized.py  # baselines: majority class + centralised training without DP
│   └── sweep.py        # full grid: 2 strategies × 5 ε × 3 runs + baselines
├── api/                # Component 4 FastAPI service (port 8004)
│   ├── main.py         # app entry point
│   ├── security.py     # bcrypt, JWT, role checks
│   ├── audit.py        # hash-chained audit log + verification
│   ├── models.py       # database tables
│   ├── schemas.py      # request/response validation
│   ├── routers/        # auth, decisions, audit, federation, FAKL-readiness endpoints
│   └── seed_users.py   # demo accounts
├── privacy/ fakl/ security/   # (planned) later phases
├── data/               # datasets (data/raw/ is git-ignored)
├── results/            # experiment CSVs + summary.csv
├── docs/               # research logbook
├── .env.example        # configuration template (copy to .env)
├── requirements.txt
├── Dockerfile          # image for the federated nodes (CPU-only PyTorch)
├── requirements-docker.txt   # packages inside that image
├── docker-compose.yml  # server + 3 clinics; PostgreSQL + Neo4j under profile "db"
└── .dockerignore
```

## Setup (Windows)

Keep the virtual environment **outside OneDrive** (OneDrive makes imports very slow):

```powershell
python -m venv C:\venvs\component4
C:\venvs\component4\Scripts\Activate.ps1
pip install -r component4\requirements.txt
copy component4\.env.example component4\.env   # then fill in the secrets
```

Leave `DATABASE_URL` empty to use a local SQLite file; set it to a PostgreSQL
URL once PostgreSQL is installed.

### Data (CP-AnemiC v2, from Component 1)

Patient images are **never** stored in the repo. Unzip the datasets to a folder outside
the repo and outside OneDrive (e.g. `C:\ayurai-data\datasets`) and set
`C4_DATA_DIR` in `component4/.env`. Then build the features file once:

```powershell
python component4/federated/prepare_data.py
```

This reads the 251 conjunctiva images and their lab haemoglobin, turns each image into
10 colour features, labels it Low / Moderate / High risk (Hb ≥ 11 / 8–10.9 / < 8) and
assigns each patient to one clinic (non-IID). Without this file, training falls back to
random placeholder data (as in Docker).

## Running

From the repository root, with the venv activated:

```powershell
# One experiment (FedAvg, ε = 2.0, run 1)
python component4/federated/run.py 2.0

# FedProx at ε = 0.5, run 2
python component4/federated/run.py 0.5 --strategy fedprox --run 2

# Reference run without differential privacy
python component4/federated/run.py --no-dp --strategy fedprox

# Baselines only: majority class + centralised training without DP
python component4/federated/centralized.py --runs 3

# Everything (≈15 minutes) → results/summary.csv and results/baselines.csv
python component4/federated/sweep.py --runs 3

# API: create demo accounts once, then start the service on port 8004
python component4/api/seed_users.py --password <demo-password>
python component4/api/main.py          # docs at http://127.0.0.1:8004/docs
```

The dashboard (`ayurai-client`) reaches the API through its Vite proxy at
`/c4-api`. Demo mode needs no sign-in; live mode requires a Component 4 account.

Demo accounts: `practitioner.clinic1`, `practitioner.clinic2`,
`practitioner.clinic3`, `supervisor`, `researcher`.

## Blockchain anchoring (Ethereum Sepolia)

The audit log is hash-chained: each entry stores the SHA-256 of the previous one. That
detects an edit to any single row, but not someone who rewrites the whole log and
recomputes every hash. Anchoring closes that gap: a supervisor writes the newest entry's
hash to the `AuditAnchor` smart contract (`security/AuditAnchor.sol`) on the Sepolia test
network. Only that 32-byte hash goes on-chain, never patient data or log records.

- **Anchor:** `POST /api/v1/c4/audit/anchor` (supervisor). Takes ~10-30 s while the block is mined.
- **Verify:** `GET /api/v1/c4/audit/anchors/verify` compares every on-chain hash with the
  database as it is now; a rewritten log no longer matches.
- **Dashboard:** Audit & governance → *Blockchain anchoring* (sign in as a supervisor).

Setup: deploy `security/AuditAnchor.sol` from a test-only wallet (e.g. with Remix), then fill
the blockchain section of `.env` (see `.env.example`). Check the connection with
`python component4/security/check_sepolia.py`; `security/test_anchor.py` sends one test anchor.

## Running with Docker

Requires Docker Desktop. Run these from the `component4/` folder.

**1. Settings.** Copy the template and choose your own passwords (never commit `.env`):

```powershell
copy .env.example .env
# then edit .env: POSTGRES_PASSWORD, NEO4J_PASSWORD (min 8 characters), EPSILON
```

**2. Federated nodes** (1 server + 3 clinic containers, FedAvg). Results are written to
`component4/results/` on your machine:

```powershell
docker compose up --build        # first run builds the image; later runs can omit --build
docker compose down              # remove the stopped containers
```

Run with a different privacy budget (Windows PowerShell):

```powershell
$env:EPSILON = "0.5"
docker compose up
Remove-Item Env:EPSILON          # go back to the value in .env
```

**3. Databases** (profile `db`, not started by the commands above):

```powershell
docker compose --profile db up -d postgres neo4j     # start in the background
docker compose --profile db stop postgres neo4j      # stop (data is kept)
```

- Neo4j browser: http://localhost:7474 (user `neo4j`, password from `.env`)
- PostgreSQL shell: `docker exec -it ayurai-postgres psql -U <POSTGRES_USER> -d ayurai_audit`
- To use the Docker PostgreSQL from the Component 4 API, set in `.env`:
  `DATABASE_URL=postgresql+psycopg2://<POSTGRES_USER>:<POSTGRES_PASSWORD>@localhost:5432/ayurai_audit`
  The API creates its tables (`users`, `decisions`, hash-chained `audit_logs`) on startup.
  Then run `python api/seed_users.py --password <choose-one>` once to create the demo accounts.

Passwords are applied only when a database is **first** created. To change them later,
delete the data volumes (this erases the databases): `docker compose --profile db down -v`.

## Status

**Working**
- FedAvg and FedProx (μ = 0.1) across 3 simulated clinics with a non-IID split
- Opacus DP calibrated over the whole run: ε spent stays within the target for all
  five budgets (0.1, 0.5, 1.0, 2.0, 5.0), δ = 10⁻⁵
- Real data: CP-AnemiC v2 (251 patients, lab Hb) via colour features; patient-level split
- Sweep with 3 runs per setting: mean ± std accuracy and macro-F1, plus baselines
  (majority class, centralised without DP, federated without DP)
- API: JWT sign-in, roles (practitioner / supervisor / researcher), clinic-scoped
  access, practitioner decisions, hash-chained audit log with tamper detection,
  service endpoint for C2/C3 audit events, federation results endpoints
- Dashboard: sign-in, decision buttons on Practitioner review, live audit ledger,
  Federated training and Privacy budget pages
- Scalability (NFR, ≥ 10 nodes): `C4_NUM_CLINICS=10` runs 10 clinic nodes with no code
  change; on 2026-10-20 all 10 joined every round and 10 rounds took 21 s (ε = 2.0, FedProx)
- Automated API tests: `python -m unittest discover component4/tests -v`
- Blockchain: audit-chain head hash anchored on the `AuditAnchor` contract (Sepolia);
  verification detects even a full rewrite of the log with recomputed hashes

**Placeholder / known limitations**
- Small dataset (251 patients, only 19 High-risk) and simple colour features: the signal
  is modest, and results vary between runs.
- Learning rate and feature scaling were chosen on pooled results; there is no separate
  validation set yet (cross-validation is future work).
- Feature-scaling statistics (per-clinic sums and counts) are shared without DP.
- Risk-tier Hb thresholds follow WHO severity bands; to be confirmed with Component 1.
- The Docker nodes still use placeholder data (the dataset is not mounted).
- SQLite is the default database; PostgreSQL is available via Docker (`DATABASE_URL`).
- Audit writes are not locked against concurrent writers (prototype).
- Anchoring is manual (a supervisor clicks it), on a public testnet; the contract owner
  cannot be changed, so a lost key means redeploying.

**Next**
- Image model (CNN, or Component 1's trained model with a DP-trained final layer)
- Cross-validation; more data (Ghana conjunctiva / fingernail sets)
- FAKL: federate practitioner-feedback changes to Component 2 claim confidence
  (designed; the dashboard's *Knowledge federation* page shows the design and a live,
  read-only readiness check of Component 2's graph via `GET /api/v1/c4/fakl/status`.
  Currently the graph has no claims or feedback, and feedback has no `clinic_id` yet)
- Component 2 / 3 posting their audit records to `/api/v1/c4/audit/events`
