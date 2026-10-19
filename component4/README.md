# Component 4 — Privacy-Preserving Federated Learning, Security & Governance

This component lets several clinics jointly train the AyurAI anemia risk model
(Low / Moderate / High) without any clinic sharing raw patient data. Training is
coordinated with [Flower](https://flower.ai/) using FedProx (proposed) and FedAvg
(baseline), and every clinic applies differential privacy with
[Opacus](https://opacus.ai/) before its model update leaves the node. A FastAPI
service adds the security and governance layer: JWT sign-in, role-based access
control, practitioner decisions and a tamper-evident (hash-chained) audit log.
Later phases add FAKL (federated Neo4j knowledge-graph weights) and Ethereum
Sepolia anchoring of the audit log.

## Folder structure

```
component4/
├── federated/          # Flower + Opacus experiments
│   ├── config.py       # shared settings: rounds, μ, δ, ε values, clinic profiles
│   ├── data.py         # per-clinic non-IID data (PLACEHOLDER until C1 data arrives)
│   ├── model.py        # anemia risk classifier
│   ├── client.py       # clinic node: DP training + FedProx proximal step
│   ├── server.py       # FedAvg / FedProx server; writes per-round CSV
│   ├── run.py          # one experiment: server + 3 clinics
│   └── sweep.py        # full grid: 2 strategies × 5 ε × 3 runs → summary.csv
├── api/                # Component 4 FastAPI service (port 8004)
│   ├── main.py         # app entry point
│   ├── security.py     # bcrypt, JWT, role checks
│   ├── audit.py        # hash-chained audit log + verification
│   ├── models.py       # database tables
│   ├── schemas.py      # request/response validation
│   ├── routers/        # auth, decisions, audit, federation endpoints
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

## Running

From the repository root, with the venv activated:

```powershell
# One experiment (FedAvg, ε = 2.0, run 1)
python component4/federated/run.py 2.0

# FedProx at ε = 0.5, run 2
python component4/federated/run.py 0.5 --strategy fedprox --run 2

# Full experiment grid (≈10 minutes) → component4/results/summary.csv
python component4/federated/sweep.py --runs 3

# API: create demo accounts once, then start the service on port 8004
python component4/api/seed_users.py --password <demo-password>
python component4/api/main.py          # docs at http://127.0.0.1:8004/docs
```

The dashboard (`ayurai-client`) reaches the API through its Vite proxy at
`/c4-api`. Demo mode needs no sign-in; live mode requires a Component 4 account.

Demo accounts: `practitioner.clinic1`, `practitioner.clinic2`,
`practitioner.clinic3`, `supervisor`, `researcher`.

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
- Sweep with 3 runs per setting and a summary of mean ± std accuracy
- API: JWT sign-in, roles (practitioner / supervisor / researcher), clinic-scoped
  access, practitioner decisions, hash-chained audit log with tamper detection,
  service endpoint for C2/C3 audit events, federation results endpoints
- Dashboard: sign-in, decision buttons on Practitioner review, live audit ledger,
  Federated training and Privacy budget pages

**Placeholder / known limitations**
- Training data is **random placeholder features**, so accuracy (≈0.33) is not
  meaningful. Waiting for the CP-AnemiC data used by Component 1.
- SQLite is used until PostgreSQL is installed.
- Audit writes are not locked against concurrent writers (prototype).

**Next**
- Connect the Component 1 dataset (CP-AnemiC) and rerun the sweep
- Ethereum Sepolia anchoring of the audit chain head hash
- FAKL: federate practitioner-feedback changes to Component 2 claim confidence
- Component 2 / 3 posting their audit records to `/api/v1/c4/audit/events`
- Centralised-training baseline
