# Deploying AyurAI on a VPS

One `docker compose` stack runs the whole site:

| Container | What it is | Reachable from |
|-----------|------------|----------------|
| `nginx` | Built dashboard (`ayurai-client`) + reverse proxy for `/c1-api` … `/c4-api` | Internet (80, 443) |
| `c1` | Component 1 API, port 8001 | Other containers only |
| `c2` | Component 2 API, port 8000 | Other containers only |
| `c3` | Component 3 API, port 8003 | Other containers only |
| `c4-api` | Component 4 API, port 8004 | Other containers only |
| `postgres` | Component 4 audit database | Other containers only |

Neo4j is not in the stack: Components 2 and 3 connect to Neo4j AuraDB using the
`NEO4J_*` values in their `.env` files. The federated-learning containers
(`component4/docker-compose.yml`) are for experiments and are not deployed.

Component 1 on a VPS: the questionnaire, browser webcam captures and image
analysis work. **PPG recording does not**: it reads the ESP32 + MAX30102 sensor
on a local USB port, which a server does not have, so that step returns an error.
Component 1 has **no sign-in** and is meant for fictional demo sessions only;
anyone who can open the site can create sessions and upload images.

Files: [`docker-compose.prod.yml`](../docker-compose.prod.yml),
[`.env.prod.example`](../.env.prod.example), [`nginx/`](nginx/), and a
`Dockerfile` in `component1/`, `component2/`, `component3/`, `ayurai-client/`, plus
`component4/Dockerfile.api`.

## 1. Server preparation (once)

Ubuntu VPS with Docker installed (`curl -fsSL https://get.docker.com | sudo sh`,
then `sudo usermod -aG docker $USER` and log in again).

Firewall: allow only SSH and the web ports.

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
```

Memory: Component 2 loads an embedding model and the first build installs
PyTorch. With less than 8 GB RAM, add swap so the build does not run out of memory:

```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. Code and secrets

```bash
git clone https://github.com/kusal2002/AyurAI-RP.git ~/ayurai && cd ~/ayurai
```

The `.env` files are git-ignored, so copy them from your PC (run in PowerShell
on the PC, replacing the IP):

```powershell
scp D:\Research\AyurAI-RP\component2\.env ubuntu@VPS_IP:~/ayurai/component2/.env
scp D:\Research\AyurAI-RP\component3\.env ubuntu@VPS_IP:~/ayurai/component3/.env
scp D:\Research\AyurAI-RP\component4\.env ubuntu@VPS_IP:~/ayurai/component4/.env
```

Windows saves these files with CRLF line endings. Convert them on the server so
no value ends with a hidden `\r` (for example in a password):

```bash
sed -i 's/\r$//' ~/ayurai/component2/.env ~/ayurai/component3/.env ~/ayurai/component4/.env
```

Each `.env` must contain at least the variables in its `.env.example`
(`component2/`, `component3/`, `component4/`). On the server, check `component4/.env`:
- `JWT_SECRET` and `C4_SERVICE_API_KEY` must be set to long random values
  (`openssl rand -hex 32`). Without `JWT_SECRET` everyone is logged out on every restart.
- `C2_NEO4J_*` give the FAKL page read access to Component 2's AuraDB.
- `DATABASE_URL` and the `POSTGRES_*` / `NEO4J_PASSWORD` lines are not used here:
  compose builds `DATABASE_URL` from `.env.prod` and points it at the `postgres` container.

### Component 1 model weights

Component 1 keeps its data in a `datasets` folder **next to** the repository
(`~/datasets` for a repo in `~/ayurai`), the same layout as on a laptop. The API
creates `live_sessions/` and `screening_sessions.sqlite3` there by itself, but the
trained models must be copied in. They are not in git; get them from the
Component 1 owner. Expected files:

```
~/datasets/trained_model_artifacts/
├── efficientnet_b0_best.pth
├── ghana_conjunctiva/resnet_50_best.pth
├── ghana_fingernail/resnet_50_best.pth
├── yakimov_hb_2024/efficientnet_b0_best.pth
└── imagehb_tongue/efficientnet_b0_best.pth
```

Create the folder on the server, then copy from the PC (PowerShell, adjust the source path):

```bash
mkdir -p ~/datasets
```

```powershell
scp -r C:\path\to\datasets\trained_model_artifacts ubuntu@VPS_IP:~/datasets/
```

Without these files the API still starts, but image analysis fails.
To use another folder, set `C1_DATASETS_DIR` in `.env.prod`.

### Stack settings

Then create the stack settings:

```bash
cp .env.prod.example .env.prod && nano .env.prod
```

Set `POSTGRES_PASSWORD` (letters and digits only, e.g. `openssl rand -hex 24`).
Set `DOMAIN` if you have one, otherwise leave `_` to use the IP.

## 3. Start

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

The first build takes a while (PyTorch). Check that everything is up:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

```bash
curl http://localhost/c1-api/api/c1/health && curl http://localhost/c2-api/health && curl http://localhost/c3-api/health && curl http://localhost/c4-api/health
```

### Sign-in accounts (Component 4)

The dashboard's sign-in page uses these demo accounts:

| Username | Role | Clinic |
|----------|------|--------|
| `practitioner.clinic1` / `.clinic2` / `.clinic3` | practitioner | clinic-1 / 2 / 3 |
| `supervisor` | supervisor | all |
| `researcher` | researcher | all |

Set `C4_SEED_PASSWORD` (8+ characters) in `component4/.env`. Every time the
`c4-api` container starts, it creates any missing accounts with that password.
Accounts that already exist keep their password. Check the result:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs c4-api | grep -E "created|exists|seed_users"
```

To change every demo account's password later:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec c4-api python seed_users.py --password 'NEW_PASSWORD' --reset-passwords
```

Open `http://VPS_IP` in a browser.

Tip: save typing with an alias in `~/.bashrc`:
`alias dc='docker compose -f ~/ayurai/docker-compose.prod.yml --env-file ~/ayurai/.env.prod'`

## 4. HTTPS (needs a domain)

1. At your DNS provider, add an `A` record for the domain pointing to the VPS IP,
   and wait until `ping your.domain` shows that IP.
2. Set `DOMAIN=your.domain` in `.env.prod` (keep `NGINX_CONF=http`) and restart nginx:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d nginx
   ```
3. Get the certificate (replace domain and email). It is stored in the server's
   `/etc/letsencrypt`, which nginx reads:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm certbot certonly --webroot -w /var/www/certbot -d your.domain --email you@example.com --agree-tos --no-eff-email
   ```
4. Set `NGINX_CONF=https` in `.env.prod` and restart nginx (same command as step 2).
5. Renew automatically: `crontab -e` and add
   ```
   0 3 * * 1 cd ~/ayurai && docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm certbot renew -q && docker compose -f docker-compose.prod.yml --env-file .env.prod exec nginx nginx -s reload
   ```

## Updating

Automatic: see "CI/CD with GitHub Actions" below. By hand, on the server:

```bash
bash ~/ayurai/deploy/remote-deploy.sh ~/ayurai
```

It pulls `main`, rebuilds, restarts and waits until every service answers.

## CI/CD with GitHub Actions

Two workflows in `.github/workflows/`:

- **CI** (`ci.yml`) runs on every pull request and push to `main` or `dev`:
  frontend lint + type check + build, the Component 4 tests, a check of
  `docker-compose.prod.yml`, a build of all five Docker images, and an nginx config test.
- **Deploy** (`deploy.yml`) runs after CI passes on a push to `main`. It connects
  to the VPS over SSH and runs `deploy/remote-deploy.sh`. It can also be started
  by hand from the Actions tab (Deploy → Run workflow).

The deploy uses `git pull --ff-only`. If files were edited directly on the
server (for example `docker-compose.prod.yml`), the deploy stops instead of
overwriting them. Commit such changes to the repository instead.

### One-time setup

1. **Create a deploy key** on your PC (no passphrase), just for GitHub Actions:
   ```bash
   ssh-keygen -t ed25519 -f ayurai_deploy -N "" -C "github-actions-deploy"
   ```
2. **Allow it on the server**: append the public key to the deploy user's
   `~/.ssh/authorized_keys` (run on the PC, replace the IP):
   ```bash
   type ayurai_deploy.pub | ssh ubuntu@VPS_IP "cat >> ~/.ssh/authorized_keys"
   ```
   (In Git Bash use `cat` instead of `type`.) The user must be in the `docker` group.
3. **Get the server's host key** (lets GitHub check it is talking to your server):
   ```bash
   ssh-keyscan -H VPS_IP
   ```
4. **Add repository secrets** on GitHub: Settings → Secrets and variables → Actions → New repository secret:

   | Secret | Value |
   |--------|-------|
   | `VPS_HOST` | server IP or domain |
   | `VPS_USER` | SSH user, e.g. `ubuntu` |
   | `VPS_SSH_KEY` | the whole content of the private key file `ayurai_deploy` |
   | `VPS_KNOWN_HOSTS` | the full output of step 3 |

   Optional variables (Variables tab): `VPS_PORT` (default 22), `VPS_APP_DIR` (default `~/ayurai`).
5. Delete the private key file from your PC once it is saved in GitHub.
6. Optional: Settings → Environments → `production` → add yourself as a
   required reviewer, so each deploy waits for your approval.

The server must already be set up once by hand (sections 1–3): the clone in
`~/ayurai`, the `.env` files, `.env.prod` and the Component 1 model weights.
The workflows never see or copy those secrets.

## Useful commands

- Logs of one service: `docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f c2`
- Restart one service: `... restart c3`
- Stop everything (data in volumes is kept): `... down`
- Database backup: `... exec postgres pg_dump -U ayurai ayurai_audit > backup.sql`
- Component 1 sessions live in `~/datasets` (back up that folder)

## Notes

- `component2/corpus/` (about 1.4 GB, git-ignored) is not in the image.
  `/health/readiness` reports the corpus manifest and candidate store as missing;
  reasoning itself uses Neo4j and the embedding model.
- `POST /api/v1/c2/feedback` writes permanent records to Neo4j AuraDB. The
  deployed site uses the same AuraDB as your laptop.
- Component 3 allows CORS from any origin; it is only reached through nginx,
  so this does not widen access.
