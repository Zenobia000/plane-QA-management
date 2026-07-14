#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || "${CONFIRM_RESTORE:-}" != "ERASE_AND_RESTORE_PLANE" ]]; then
  echo "Usage: CONFIRM_RESTORE=ERASE_AND_RESTORE_PLANE $0 <backup-directory>" >&2
  exit 2
fi
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="$(cd "$1" && pwd)"
cd "$ROOT_DIR"
(cd "$BACKUP_DIR" && sha256sum --check SHA256SUMS)
export PLANE_TESTING_TAG="${PLANE_TESTING_TAG:-$(git rev-parse --short "$(cat "$BACKUP_DIR/source-commit.txt")")}"
set -a
source .env
set +a
COMPOSE=(docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml)

"${COMPOSE[@]}" stop api worker beat-worker web
"${COMPOSE[@]}" exec -T plane-db psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB" \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
gzip -dc "$BACKUP_DIR/postgres.sql.gz" | "${COMPOSE[@]}" exec -T plane-db psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"
docker run --rm --volumes-from plane-minio alpine:3.22 sh -c 'find /export -mindepth 1 -delete'
gzip -dc "$BACKUP_DIR/minio.tar.gz" | docker run --rm -i --volumes-from plane-minio alpine:3.22 tar -C /export -xf -
"${COMPOSE[@]}" run --rm migrator
"${COMPOSE[@]}" up -d plane-db plane-redis plane-mq plane-minio api web worker beat-worker
echo "Restore complete; run the documented smoke and acceptance checks."
