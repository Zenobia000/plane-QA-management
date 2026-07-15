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

## Quick Reference

| What | Where |
|---|---|
| App / login | http://localhost:8787 |
| Instance admin | http://localhost:8787/god-mode |
| Public spaces | http://localhost:8787/spaces |
| API | http://localhost:8787/api |
| Stop / start / logs | `docker compose stop` / `up -d` / `logs -f api` |
| First-time account | First signup becomes instance admin |

## Common Mistakes

| Symptom | Cause → Fix |
|---|---|
| `proxy` container `Restarting`, log says "server block without any key" | `SITE_ADDRESS` missing in `.env` or compose config → step 1 |
| `plane-live` `Restarting`, log says "Invalid environment variables" | `apps/api/.env` missing `LIVE_SERVER_SECRET_KEY` or `REDIS_URL` → step 1 |
| `port is already allocated` on 8000/5432 | Used `docker-compose-local.yml` → use full stack instead |
| API 500s / signup mails point to localhost | `apps/api/.env` missing or has default URLs → step 1 |
| Root `.env` lost 8787/LAN-IP settings | Someone ran `setup.sh` → restore the URL/proxy lines in step 1 |
