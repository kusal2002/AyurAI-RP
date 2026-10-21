#!/usr/bin/env bash
# Runs ON THE VPS (sent over SSH by .github/workflows/deploy.yml, or run by hand):
#   bash deploy/remote-deploy.sh ~/ayurai
# Pulls main, rebuilds and restarts the stack, then waits until every service answers.
set -euo pipefail

APP_DIR="${1:-$HOME/ayurai}"
cd "$APP_DIR"

compose() { docker compose -f docker-compose.prod.yml --env-file .env.prod "$@"; }

echo "==> Updating code in $APP_DIR"
git fetch --prune origin
git checkout main
# Fails (and stops the deploy) if files were edited on the server, instead of overwriting them
git pull --ff-only origin main
git log --oneline -1

echo "==> Building and starting containers"
compose up -d --build --remove-orphans

echo "==> Waiting for services"
# Checked from inside the nginx container, so it works with or without HTTPS
check() { compose exec -T nginx wget -q -T 5 -O /dev/null "$1"; }
services=(
  "c1 http://c1:8001/api/c1/health"
  "c2 http://c2:8000/health"
  "c3 http://c3:8003/health"
  "c4-api http://c4-api:8004/health"
)
for entry in "${services[@]}"; do
  name="${entry%% *}"; url="${entry#* }"
  for attempt in $(seq 1 36); do          # up to 3 minutes per service
    if check "$url"; then echo "    ok: $name"; break; fi
    if [ "$attempt" -eq 36 ]; then
      echo "    FAILED: $name did not answer at $url" >&2
      compose logs --tail 50 "$name" >&2 || true
      exit 1
    fi
    sleep 5
  done
done

# The website itself: nginx config loads and the built dashboard is in place.
# (Not fetched over HTTP: with HTTPS on, the redirect to https://localhost fails the certificate check.)
compose exec -T nginx nginx -t -q
compose exec -T nginx test -f /usr/share/nginx/html/index.html
echo "    ok: web"

echo "==> Removing old images"
docker image prune -f >/dev/null

echo "==> Deployed"
