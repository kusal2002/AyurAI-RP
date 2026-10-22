# Running Component 4 (for teammates)

Component 4 = privacy, security & governance: the governance API (sign-in, practitioner
decisions, tamper-evident audit log, federated-learning results, FAKL) and its pages in the
shared dashboard (`ayurai-client`).

**What runs where today**

| Part | How it runs |
|---|---|
| PostgreSQL database | Docker |
| Federated server + 3 clinic nodes | Docker (placeholder data, see step 6) |
| Component 4 API (port 8004) | Python (not containerised yet) |
| Dashboard (port 5173) | `npm run dev` in `ayurai-client` |

Commands are for Windows **Command Prompt (cmd)**, run from the repository root unless stated.
(macOS/Linux: use `/` in paths and `source <venv>/bin/activate` instead of `activate.bat`.)

---

## 0. Prerequisites (once)

- **Docker Desktop**, open and showing *Engine running*
- **Python 3.11** (recommended) and **Node.js 22**
- **The code.** Until the Component 4 pull request is merged into `dev`, it is on the branch
  `vageesha/component4/fakl`. Commit or stash your own work first, then:

  ```
  git fetch origin
  git switch vageesha/component4/fakl
  ```

  After the merge, just use `dev` (`git switch dev` then `git pull`).

## 1. Create your settings file (once)

```
copy component4\.env.example component4\.env
```

Open `component4\.env` and fill in **your own** values (never commit this file; it is git-ignored):

| Setting | What to put |
|---|---|
| `POSTGRES_PASSWORD` | Any password you choose (letters, digits, `-`, `_` only) |
| `NEO4J_PASSWORD` | Any password, at least 8 characters |
| `DATABASE_URL` | `postgresql+psycopg2://ayurai:<your POSTGRES_PASSWORD>@127.0.0.1:5432/ayurai_audit` |
| `JWT_SECRET` | Output of `python -c "import secrets; print(secrets.token_hex(32))"` |

Also replace `CHANGE_ME` in `POSTGRES_PASSWORD` / `NEO4J_PASSWORD` with your own values.

Leave the **blockchain** (`SEPOLIA_*`, `WALLET_*`, `CONTRACT_ADDRESS`) and **`C2_NEO4J_*`** lines empty
(as in the example): they need private credentials. Without them the API still runs; blockchain
anchoring and the FAKL readiness check simply show "unavailable" / "not configured".

> Use `127.0.0.1`, not `localhost`, for the database: the container listens on IPv4 only.

## 2. Start the database (Docker)

```
cd component4
docker compose --profile db up -d postgres
cd ..
```

Expected: `Container ayurai-postgres Started`. It keeps running in the background
(stop it with `docker compose --profile db stop postgres` from `component4`).

## 3. Install the API's packages (once, about 2 minutes)

Use a virtual environment **outside OneDrive** (OneDrive makes Python very slow):

```
python -m venv C:\venvs\component4
C:\venvs\component4\Scripts\activate.bat
pip install fastapi==0.138.2 uvicorn==0.49.0 SQLAlchemy==2.1.5 psycopg2-binary==2.9.13 PyJWT==2.15.1 bcrypt==5.0.0 python-dotenv==1.2.4 web3==8.0.0 neo4j==6.4.1 numpy==2.4.6
```

(This is the API-only set. `component4\requirements.txt` has everything, including PyTorch for
federated training, about 2 GB.)

## 4. Create demo accounts (once)

```
C:\venvs\component4\Scripts\activate.bat
python component4\api\seed_users.py --password <choose-a-demo-password>
```

Creates `practitioner.clinic1`, `practitioner.clinic2`, `practitioner.clinic3`, `supervisor` and
`researcher`, all with that password.

## 5. Run the API and the dashboard (each time)

**Terminal 1, API** (keep it open):

```
C:\venvs\component4\Scripts\activate.bat
python component4\api\main.py
```

Expected: `Uvicorn running on http://127.0.0.1:8004`. API docs: http://127.0.0.1:8004/docs

**Terminal 2, dashboard** (keep it open):

```
cd ayurai-client
npm ci
npm run dev
```

(`npm ci` only the first time.) Open **http://localhost:5173**, click **Sign in**, use one of the
demo accounts. Component 4 pages are under **Governance** in the sidebar: *Federated training*,
*Privacy budget*, *Knowledge federation*, *Audit & governance*; plus *Practitioner review*.

## 6. Optional: federated training nodes in Docker

```
cd component4
docker compose up --build
```

Starts 1 server + 3 clinic containers, trains for 10 rounds and writes a CSV to
`component4\results\`. It uses **placeholder data**: the real CP-AnemiC dataset is not in the
repo (patient images) and not mounted into the containers. The first build downloads about 2 GB.

## 7. Optional: FAKL prototype (no servers needed)

```
C:\venvs\component4\Scripts\activate.bat
python component4\fakl\run_fakl.py
```

Prints how the federated knowledge-graph update compares with central pooling (synthetic data).

## Stopping

`Ctrl+C` in the API and dashboard terminals. Database: `docker compose --profile db stop postgres`
(from `component4`); your data is kept.

## Troubleshooting

| Problem | Fix |
|---|---|
| API: `connection refused` / `could not connect` | Database not running: repeat step 2 (Docker Desktop must be open) |
| API: `password authentication failed` | `DATABASE_URL` password differs from `POSTGRES_PASSWORD` |
| Changed `POSTGRES_PASSWORD` later and sign-in to the database fails | The password is set when the database is first created. Reset (deletes the data): `docker compose --profile db down -v`, then steps 2 and 4 |
| `No module named …` | Activate the venv first (`C:\venvs\component4\Scripts\activate.bat`) |
| `address already in use` (8004 or 5173) | It is already running in another terminal |
| Dashboard: "Component 4 … could not be reached" | Terminal 1 (API) is not running |
| Blockchain / FAKL readiness "unavailable" | Expected without the private credentials (step 1) |

`component4\start-demo.bat` and `demo-runs.bat` are the component owner's shortcuts for the same
steps; they assume the venv at `C:\venvs\component4`.
