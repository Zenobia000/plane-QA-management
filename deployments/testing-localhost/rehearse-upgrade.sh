#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
BACKUP_DIR="${1:-$ROOT_DIR/backups/upgrade-rehearsal-$(date -u +%Y%m%dT%H%M%SZ)}"
deployments/testing-localhost/backup.sh "$BACKUP_DIR"
export PLANE_TESTING_TAG="rehearsal-$(git rev-parse --short HEAD)"
COMPOSE=(docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml)
"${COMPOSE[@]}" build web api
"${COMPOSE[@]}" run --rm migrator
"${COMPOSE[@]}" up -d plane-db plane-redis plane-mq plane-minio api web worker beat-worker
"${COMPOSE[@]}" exec -T api python manage.py check --deploy
"${COMPOSE[@]}" exec -T web sh -c 'for i in $(seq 1 12); do wget -qO /dev/null http://127.0.0.1:3000/ && exit 0; sleep 5; done; exit 1'
"${COMPOSE[@]}" exec -T web sh -c 'for i in $(seq 1 12); do wget -qO /dev/null http://api:8000/ && exit 0; sleep 5; done; exit 1'
echo "Upgrade rehearsal passed. Recovery point: $BACKUP_DIR"
