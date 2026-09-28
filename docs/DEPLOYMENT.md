# Deployment Notes

## Local container

`Dockerfile` installs the Python dependencies and starts Uvicorn on port 8000. `docker-compose.yml` mounts the source read-only and persists `/data` for the prototype database.

## Production container

Build the image with a pinned Python base, run as a non-root user, mount secrets through the orchestrator, and terminate TLS at an ingress/load balancer. Use a managed PostgreSQL/PostGIS database, Redis, object storage, and a queue rather than the SQLite volume. Set `ENVIRONMENT=production`, a long random `SECRET_KEY`, `COOKIE_SECURE=true`, `SEED_DEMO_DATA=false`, `SIMULATOR_ENABLED=false`, and `HEARTBEAT_ENABLED=false`; startup rejects unsafe production combinations. Real deployments should send camera health through the authenticated heartbeat endpoint or a regional gateway rather than enabling the synthetic collector. Set `MAP_TILE_URL` and `MAP_ATTRIBUTION` to the approved public tile provider or self-hosted service; do not rely on the low-volume OpenStreetMap default for a high-traffic deployment.

## Map tile delivery

Keep the response `Referrer-Policy` at `strict-origin-when-cross-origin` so the browser sends the required origin to a public tile provider. Do not replace it with `same-origin` or `no-referrer`, strip the header at a proxy, add cache-busting parameters, or implement bulk/offline tile prefetching. Verify the provider’s current terms and attribution requirements at deployment time.

## Database migration

The prototype creates tables with SQLAlchemy `create_all`, which is convenient for a demo. Before production, adopt Alembic or another migration tool, use [`sql/postgres_postgis.sql`](../sql/postgres_postgis.sql) as the PostgreSQL/PostGIS baseline, backfill the optional `location` geography column, seed only approved reference data, and apply least-privilege database roles.

## Health checks

Use `/api/v1/system/readiness` for readiness and `/api/v1/system/health` for liveness. A production probe should also check the queue, database connection pool, storage, and realtime fan-out without exposing secrets.

## Reverse proxy requirements

Set `COOKIE_SECURE=true`, preserve WebSocket upgrade headers, disable buffering for SSE, set a reasonable request-size limit, and use a request ID header. Do not log authorization headers, cookies, stream URLs, or event payloads containing sensitive identifiers.
