#!/bin/bash
# Run the celery worker natively. Only needed when exercising async paths
# (notifications, exports, seeding); most API work doesn't require it.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  echo "apps/api/.env is missing. Create it with: tr -d '\r' < .env.example > .env" >&2
  exit 1
fi
# tr strips CRLF in case .env was saved from Windows
set -a
source <(tr -d '\r' < .env)
# .env.local is a gitignored, optional overlay. .env carries the compose
# hostnames (plane-db, plane-redis, plane-mq), which only resolve inside the
# docker network, so a native run overrides them to localhost here.
if [[ -f .env.local ]]; then
  source <(tr -d '\r' < .env.local)
fi
set +a
export DJANGO_SETTINGS_MODULE=plane.settings.local
VENV="${PLANE_VENV:-$HOME/.venvs/plane-qa-api}"
exec "$VENV/bin/celery" -A plane worker -l info
