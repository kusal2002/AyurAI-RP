# Deploying AyurAI on a VPS

One `docker compose` stack runs the whole site:

| Container | What it is | Reachable from |
|-----------|------------|----------------|
| `nginx` | Built dashboard (`ayurai-client`) + reverse proxy for `/c2-api`, `/c3-api`, `/c4-api` | Internet (80, 443) |
| `c2` | Component 2 API, port 8000 | Other containers only |
| `c3` | Component 3 API, port 8003 | Other containers only |
| `c4-api` | Component 4 API, port 8004 | Other containers only |
| `postgres` | Component 4 audit database | Other containers only |

Neo4j is not in the stack: Components 2 and 3 connect to Neo4j AuraDB using the
`NEO4J_*` values in their `.env` files. The federated-learning containers
(`component4/docker-compose.yml`) are for experiments and are not deployed.

Component 1 is not deployed either. Its API reads sessions from a `datasets`
folder next to the repository and records PPG from an ESP32 sensor on a local USB
port, which a VPS does not have. nginx answers `/c1-api` with a 503 JSON error,
so the Component 1 screens show the service as unavailable.

Files: [`docker-compose.prod.yml`](../docker-compose.prod.yml),
[`.env.prod.example`](../.env.prod.example), [`nginx/`](nginx/), and a
`Dockerfile` in `component2/`, `component3/`, `ayurai-client/`, plus
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
curl http://localhost/c2-api/health && curl http://localhost/c3-api/health && curl http://localhost/c4-api/health
```

Create the Component 4 demo accounts once:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec c4-api python seed_users.py --password 'CHOOSE_A_PASSWORD'
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
3. Get the certificate (replace domain and email):
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm certbot certonly --webroot -w /var/www/certbot -d your.domain --email you@example.com --agree-tos --no-eff-email
   ```
4. Set `NGINX_CONF=https` in `.env.prod` and restart nginx (same command as step 2).
5. Renew automatically: `crontab -e` and add
   ```
   0 3 * * 1 cd ~/ayurai && docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm certbot renew -q && docker compose -f docker-compose.prod.yml --env-file .env.prod exec nginx nginx -s reload
   ```

## Updating

```bash
cd ~/ayurai && git pull && docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Useful commands

- Logs of one service: `docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f c2`
- Restart one service: `... restart c3`
- Stop everything (data in volumes is kept): `... down`
- Database backup: `... exec postgres pg_dump -U ayurai ayurai_audit > backup.sql`

## Notes

- `component2/corpus/` (about 1.4 GB, git-ignored) is not in the image.
  `/health/readiness` reports the corpus manifest and candidate store as missing;
  reasoning itself uses Neo4j and the embedding model.
- `POST /api/v1/c2/feedback` writes permanent records to Neo4j AuraDB. The
  deployed site uses the same AuraDB as your laptop.
- Component 3 allows CORS from any origin; it is only reached through nginx,
  so this does not widen access.
