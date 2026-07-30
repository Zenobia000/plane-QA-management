#!/bin/bash
# Run the celery worker natively. Only needed when exercising async paths
# (notifications, exports, seeding); most API work doesn't require it.
set -euo pipefail
cd "$(dirname "$0")/.."
# tr strips CRLF in case .env was saved from Windows
set -a
source <(tr -d '\r' < .env)
source <(tr -d '\r' < .env.local)
set +a
export DJANGO_SETTINGS_MODULE=plane.settings.local
VENV="${PLANE_VENV:-$HOME/.venvs/plane-qa-api}"
exec "$VENV/bin/celery" -A plane worker -l info
