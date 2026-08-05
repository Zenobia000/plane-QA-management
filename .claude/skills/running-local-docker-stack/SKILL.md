---
name: running-local-docker-stack
description: Use when starting, restarting, rebuilding, or verifying the Plane QA app with Docker Compose, including first-time cold start, project-built image rebuilds, migrations, missing apps/api/.env, or port 8000/5432 already-in-use conflicts.
---

# Running the Local Docker Stack

## Overview

Run the **full stack** via `docker-compose.yml`. Everything stays on the internal Docker network; only the Caddy proxy is published on host port **8787** (`LISTEN_HTTP_PORT` in root `.env`). The app services use project-built images named `plane-testing/*:<git-sha>`.

**Do NOT use `docker-compose-local.yml`** on this machine — it publishes 8000 (taken by `triton`) and 5432 (taken by `quant-timescaledb`), so `up` fails with "port is already allocated".

**Do NOT run `setup.sh` if `.env` files already exist** — it copies `.env.example` over them, clobbering the customized root `.env` and `apps/api/.env`.

## Steps

### 0. Already running? Verify only

```bash
docker compose ps -a
```

If the containers are already Up (see step 3 for the expected state), skip straight to step 3's checks. Do not rerun a full build unless source or Docker configuration changed.

### 1. Ensure env files exist

Root `.env` must contain reachable URL and proxy settings (already set up; recreate from `.env.example` + these lines if missing):

```
LISTEN_HTTP_PORT=8787
WEB_URL=http://HOST_OR_LAN_IP:8787
APP_BASE_URL=http://HOST_OR_LAN_IP:8787
USE_MINIO=1
SITE_ADDRESS=:80
TRUSTED_PROXIES=0.0.0.0/0
```

`apps/api/.env` (gitignored) — if missing, create it:

```bash
HOST_ORIGIN="http://HOST_OR_LAN_IP:8787"
cp apps/api/.env.example apps/api/.env && sed -i \
  -e "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=\"${HOST_ORIGIN},http://localhost:8787\"|" \
  -e "s|^WEB_URL=.*|WEB_URL=\"${HOST_ORIGIN}\"|" \
  -e 's|^USE_MINIO=.*|USE_MINIO=1|' \
  -e 's|^AWS_S3_ENDPOINT_URL=.*|AWS_S3_ENDPOINT_URL="http://plane-minio:9000"|' \
  -e "s|^APP_BASE_URL=.*|APP_BASE_URL=\"${HOST_ORIGIN}\"|" \
  -e 's|^ADMIN_BASE_URL=.*|ADMIN_BASE_URL=""|' \
  -e 's|^SPACE_BASE_URL=.*|SPACE_BASE_URL=""|' \
  -e 's|^LIVE_BASE_URL=.*|LIVE_BASE_URL=""|' \
  apps/api/.env && \
echo "SECRET_KEY=\"$(tr -dc 'a-z0-9' < /dev/urandom | head -c50)\"" >> apps/api/.env
```

Empty `*_BASE_URL` values are intentional: the API then builds admin/space/live URLs from `WEB_URL` + base path, matching the proxy routes.

### 2. Build, migrate, and start

```bash
export PLANE_IMAGE_TAG="$(git rev-parse --short HEAD)"
docker compose build web admin space live api proxy
docker compose run --rm migrator
docker compose up -d
```

First cold build takes 10–20 min (four frontend images + API). `docker compose ps` may not change until images finish building — that is normal, not a hang.

### 3. Verify

Give containers ~30 s after start for health checks to settle (web/admin/space flip to `(healthy)`).

```bash
docker compose ps -a
docker logs plane-migrator 2>&1 | tail -2   # migrations "... OK"
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8787/            # 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8787/god-mode/   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8787/spaces/     # 200
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8787/live/health # 200
curl -s http://localhost:8787/api/instances/ | head -c 120                 # JSON config
```

If external access uses a LAN IP, keep root `.env` and `apps/api/.env` aligned (`WEB_URL`, `APP_BASE_URL`, `CORS_ALLOWED_ORIGINS`). If the machine's IP changes, update those values and run `docker compose up -d` again. Frontends use relative URLs, so no image rebuild is needed for URL-only changes.

### 4. Backend tests — a separate stack, never the running one

`docker-compose-test.yml` brings up its own Postgres/Valkey/RabbitMQ/MinIO on tmpfs. Use a distinct project name so it cannot collide with the app stack:

```bash
M=$(git rev-parse --show-toplevel)
docker compose -f $M/docker-compose-test.yml -p plane-merged-test --project-directory $M \
  run --rm api-tests pytest -m "unit or contract" -q
```

Subsets: append a path (`pytest plane/tests/contract/app/test_noticeboard.py`), or `-m unit`. Add `--create-db` after a migration change — the test DB is reused between runs and a stale schema shows up as errors that look like code bugs. `ruff check .` runs in the same container and is **not** covered by the pre-commit hook, which only lints JS/TS — run it before pushing backend changes.

### 5. Generating a migration

`manage.py makemigrations` must run in a container, and the file it writes is owned by root on the host — git will see it as unreadable or refuse to stage it:

```bash
docker compose -f $M/docker-compose-test.yml -p plane-merged-test --project-directory $M \
  run --rm api-tests python manage.py makemigrations db
docker run --rm -v "$M/apps/api/plane/db/migrations:/m" alpine chown -R $(id -u):$(id -g) /m
```

Then check the graph has one leaf: `manage.py showmigrations db`. Two migrations sharing a number — which happens whenever a branch is cut before another one lands — makes Django refuse to run _any_ migration, and the error names neither file helpfully.

Two ways out, and picking the wrong one causes an outage:

| Has the migration been applied anywhere you don't control? | Do this                                                                                                |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| No — only your machine, nobody has pulled it               | **Renumber** your migration and repoint its `dependencies`. Keeps the chain linear.                    |
| Yes — a colleague's DB, staging, production                | **`makemigrations --merge`**. Writes a migration whose only content is `dependencies = [both leaves]`. |

Renaming a migration that is already recorded elsewhere makes Django see it as unapplied and re-run it — `column already exists`, and someone has to `--fake` it by hand. Renumbering also leaves orphan rows in `django_migrations` on any database that recorded the old name, including your own: after renumbering, delete them (match recorded names against files on disk; do not delete by memory) or `showmigrations` keeps listing migrations that no longer exist.

Rule of thumb: **repoint before you push, merge migration after.**

### 6. Seed a project to look at

A freshly migrated instance has no data, and every panel renders its empty state. Sign up (first
account becomes instance admin), create a workspace, then:

```bash
docker compose exec api python manage.py seed_testing_demo --workspace <slug>       # DEMO
docker compose exec api python manage.py seed_ai_software_demo --workspace <slug>   # AIDEMO
```

`DEMO` is the one to use for process, states, coverage and the Overview; `AIDEMO` for custom-field
kinds and evidence attachments (add `--skip-attachments` if MinIO is not reachable). Re-running
needs `--force`, which **deletes** the existing project of that identifier along with the
workspace-level initiative and view the seed owns — never against a project someone has edited by
hand. Details: `.agents/skills/plane-qa/references/demo-data.md`.

A seeded project only ever holds what the seed held the day it ran; after pulling changes under
`apps/api/plane/testing/demo/`, re-seed rather than wondering why the docs describe rows you cannot
find.

## Quick Reference

| What                | Where                                                                                        |
| ------------------- | -------------------------------------------------------------------------------------------- |
| App / login         | http://localhost:8787                                                                        |
| Instance admin      | http://localhost:8787/god-mode                                                               |
| Public spaces       | http://localhost:8787/spaces                                                                 |
| API                 | http://localhost:8787/api                                                                    |
| Seed demo data      | `docker compose exec api python manage.py seed_testing_demo --workspace <slug>` (step 6)     |
| Stop / start / logs | `docker compose stop` / `up -d` / `logs -f api`                                              |
| Backend tests       | `docker-compose-test.yml` with `-p plane-merged-test` (step 4)                               |
| Frontend checks     | `pnpm --filter web run check:types` / `run test`; `pnpm --filter @plane/i18n run sync:check` |
| First-time account  | First signup becomes instance admin                                                          |

Changing a `packages/*` type or service needs `pnpm --filter @plane/types run build` (and `@plane/services`) before `check:types` sees it — the web app imports the built `dist`, so a source-only edit typechecks against a stale copy.

## Common Mistakes

| Symptom                                                                 | Cause → Fix                                                                                                                       |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `proxy` container `Restarting`, log says "server block without any key" | `SITE_ADDRESS` missing in `.env` or compose config → step 1                                                                       |
| `plane-live` `Restarting`, log says "Invalid environment variables"     | `apps/api/.env` missing `LIVE_SERVER_SECRET_KEY` or `REDIS_URL` → step 1                                                          |
| `port is already allocated` on 8000/5432                                | Used `docker-compose-local.yml` → use full stack instead                                                                          |
| API 500s / signup mails point to localhost                              | `apps/api/.env` missing or has default URLs → step 1                                                                              |
| Root `.env` lost 8787/LAN-IP settings                                   | Someone ran `setup.sh` → restore the URL/proxy lines in step 1                                                                    |
| `Conflicting migrations detected; multiple leaf nodes`                  | Two branches numbered a migration the same → renumber if unpushed, `makemigrations --merge` if already applied elsewhere (step 5) |
| `showmigrations` lists a migration with no file                         | Left behind by a renumber → delete those `django_migrations` rows, matching recorded names against files on disk                  |
| Migration file can't be staged / permission denied                      | Written as root inside the container → `chown` it back (step 5)                                                                   |
| `check:types` fails on a field you just added to `@plane/types`         | Web imports the built `dist` → rebuild the package first                                                                          |
| Panels render blank with no error                                       | A 5xx the UI swallows into an empty state → `docker compose logs api`, and check `test_endpoint_smoke.py` covers the route        |
