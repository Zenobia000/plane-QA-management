# Production deploy — GCP Compute Engine

The production instance is a **single Compute Engine VM** running all twelve
services under Docker Compose.

|            |                                                         |
| ---------- | ------------------------------------------------------- |
| Instance   | `plane-qa`, e2-small (2 GB), zone `asia-east1-a`        |
| Project    | `cedar-scope-489604-g3`                                 |
| Address    | http://104.199.217.106 — bare static IP, HTTP only      |
| Deploy dir | `~/plane-qa` on the VM                                  |
| Registry   | `asia-east1-docker.pkg.dev/cedar-scope-489604-g3/plane` |

It replaced an earlier Raspberry Pi deployment, which is retired.

SSH is **IAP-only** — the firewall opens 80/443 to the world and 22 only to the
IAP range:

```bash
gcloud compute ssh plane-qa --zone=asia-east1-a --tunnel-through-iap
```

`~/plane-qa` holds this directory's `docker-compose.yml`, plus `.env` and
`apps/api/.env`. **Secrets are generated on the VM and never committed.**

## Images: Cloud Build, never the VM

VMs in `asia-east1` are amd64, and an e2-small cannot build a Node monorepo
anyway. `cloudbuild.yaml` at the repo root builds all six images
(`web`, `admin`, `space`, `live`, `api`, `proxy`) and pushes them to Artifact
Registry. The `api` image also serves `worker`, `beat-worker` and `migrator`.

Images take their URLs from the runtime environment rather than build args, so an
image is address-agnostic: changing the site address touches `.env` only and
needs no rebuild.

The Compute Engine default service account is both the build runtime and the VM's
pull identity, so it needs `roles/cloudbuild.builds.builder` and
`roles/artifactregistry.writer`.

## Deploying a new version

**1. Build and push the images** (from a clean checkout of what you want to ship):

```bash
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_TAG="$(git rev-parse --short HEAD)" \
  --project=cedar-scope-489604-g3
```

**2. On the VM**, point the compose file at the new tag and roll it out:

```bash
gcloud compute ssh plane-qa --zone=asia-east1-a --tunnel-through-iap
cd ~/plane-qa

# Bump PLANE_IMAGE_TAG to the sha you just built.
$EDITOR .env

# VM pulls authenticate with the metadata token, not gcloud.
curl -H 'Metadata-Flavor: Google' \
  'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' \
  | docker login -u oauth2accesstoken --password-stdin https://asia-east1-docker.pkg.dev

docker compose pull
docker compose run --rm migrator   # explicitly, and BEFORE up -d
docker compose up -d
```

`depends_on` does **not** wait for the migrator to finish, which is why it runs as
its own step.

## Living on 2 GB

All services share 2 GB plus a 4 GB swap file. Steady state is healthy — roughly
370 MB free with swap around 280 MB and stable — but boot is not.

- **`GUNICORN_WORKERS=1`** in `apps/api/.env`. Keep it minimal.
- **api boot takes 5–7 minutes**, not 2. The single UvicornWorker imports the
  whole Django app while swapping, and `/api/instances/` returns **502 until it
  finishes**. This is normal. **Do not restart it** — you will only start the
  clock over.
- Confirm with `docker compose logs api | grep 'Listening at'`, then hit the
  endpoint **through the proxy**. The api alpine image has **no `curl`**, so
  `docker compose exec api curl …` always returns `000` — a false negative, not a
  failure.

If 2 GB genuinely bites, resize with no data loss (same disk, ~2 min):

```bash
gcloud compute instances stop plane-qa --zone=asia-east1-a
gcloud compute instances set-machine-type plane-qa --zone=asia-east1-a --machine-type=e2-medium
gcloud compute instances start plane-qa --zone=asia-east1-a
```

## Cost and gaps

Roughly **NT$630/month**. E2 machine types get **no sustained-use discount**, so
24/7 is billed at full on-demand; the only lever is a 1-year committed use
discount.

Not yet set up:

- **A domain and HTTPS.** The Caddy proxy already supports it — point a domain at
  the IP and set `SITE_ADDRESS` and `CERT_EMAIL`.
- **Database backups and disk snapshots.**
