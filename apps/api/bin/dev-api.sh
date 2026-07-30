#!/bin/bash
# Run the Django API natively against dockerized infra.
# Prereq: docker compose -f docker-compose.yml -f docker-compose-dev-ports.yml up -d --no-deps plane-db plane-redis plane-mq plane-minio
set -euo pipefail
cd "$(dirname "$0")/.."
# tr strips CRLF in case .env was saved from Windows
set -a
source <(tr -d '\r' < .env)
source <(tr -d '\r' < .env.local)
set +a
export DJANGO_SETTINGS_MODULE=plane.settings.local
PY="${PLANE_VENV:-$HOME/.venvs/plane-qa-api}/bin/python"
"$PY" manage.py wait_for_db
"$PY" manage.py wait_for_migrations
exec "$PY" manage.py runserver 0.0.0.0:8000
