# Plane Testing localhost fork

This overlay tags the root repository's source builds instead of pulling official Plane application images. PostgreSQL,
Valkey, RabbitMQ and MinIO remain pinned infrastructure images from the upstream compose file.

```bash
export PLANE_TESTING_TAG="$(git rev-parse --short HEAD)"
docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml build web api
docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml run --rm migrator
docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml up -d
docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml ps
```

Workers and migrator share the exact API image tag, so schema, web process and asynchronous artifact handling cannot
silently drift. Run `backup.sh` before migration or upstream merge. A restore intentionally requires an explicit phrase.

Smoke checks after startup:

```bash
curl --fail http://localhost:${LISTEN_HTTP_PORT:-80}/
docker compose -f docker-compose.yml -f deployments/testing-localhost/compose.source.yml exec -T api \
  python manage.py showmigrations db
```

This localhost profile publishes HTTP on `http://10.137.80.63:8787` by default. Keep `WEB_URL` and `APP_BASE_URL`
aligned with the externally reachable address so authentication redirects stay on the same origin.

The application contract suite requires a Docker-enabled account. Do not mark migration, restore or upgrade WBS gates
complete from image compilation alone.
