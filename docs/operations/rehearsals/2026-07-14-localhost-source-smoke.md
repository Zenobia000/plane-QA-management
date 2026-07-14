# Localhost source-image smoke — 2026-07-14

Scope: WBS 7.2 source-built deployment and the migration/runtime portion of the Testing platform exit gates.

## Environment

- Source baseline: `d3d3de44c`
- API image: `plane-testing-api:d3d3de44c`
- Web image: `plane-testing-web:d3d3de44c`
- Docker server: 25.0.5
- Compose files: `docker-compose.yml` plus `deployments/testing-localhost/compose.source.yml`

## Evidence

1. `docker compose ... build web api` completed with both source images built.
2. `docker compose ... run --rm migrator` completed successfully on a new PostgreSQL volume.
3. Testing migrations `db.0122_testing_library` through `db.0125_testing_automation` were applied and subsequently
   reported as `[X]` by `showmigrations db` inside the running API container.
4. The API, Web, workers, PostgreSQL, Valkey, RabbitMQ, MinIO, Live, Admin, Space, and Caddy proxy containers started.
5. Web reported healthy, Web-to-API HTTP was reachable, and `curl http://127.0.0.1/` returned HTTP 200 through Caddy.
6. Live connected to Valkey, completed HocusPocus setup, and listened on port 3000.

## Findings and corrections

- Caddy 2.11 rejects a global options block placed after a snippet. `apps/proxy/Caddyfile.ce` now places the global
  block first.
- Host `.env` values are not automatically container environment values. Compose now explicitly passes Caddy site,
  certificate, and trusted-proxy settings.
- Live previously restarted because `API_BASE_URL` and `LIVE_SERVER_SECRET_KEY` were absent. It now reads the existing
  API environment file and uses the internal API service URL.

## Not covered

This smoke alone does not prove a destructive PostgreSQL/MinIO restore, an upgrade from a sanitized current dataset, an
upstream merge, or the complete authenticated browser acceptance journeys. The later restore drill is recorded in
`2026-07-14-backup-restore.md`, and the later schema upgrade in `2026-07-14-upgrade-migration.md`; WBS 7.5 remains
non-`DONE`.
