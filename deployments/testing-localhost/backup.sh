#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"
set -a
source .env
set +a

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${1:-$ROOT_DIR/backups/plane-$STAMP}"
mkdir -p "$DEST"
COMPOSE=(docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml)

"${COMPOSE[@]}" exec -T plane-db pg_dump --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip -9 > "$DEST/postgres.sql.gz"
docker run --rm --volumes-from plane-minio alpine:3.22 tar -C /export -cf - . | gzip -9 > "$DEST/minio.tar.gz"
git rev-parse HEAD > "$DEST/source-commit.txt"
"${COMPOSE[@]}" config > "$DEST/compose.resolved.yml"
(cd "$DEST" && sha256sum postgres.sql.gz minio.tar.gz source-commit.txt compose.resolved.yml > SHA256SUMS)
echo "Backup written to $DEST"
