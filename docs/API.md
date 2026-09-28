# API Reference

Interactive documentation is generated from the application at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Authentication

`POST /api/v1/auth/login` accepts JSON:

```json
{"username":"admin","password":"ChangeMe123!"}
```

The response includes an access token and sets an HTTP-only `okdriver_token` cookie. Send the cookie with browser requests or use:

```text
Authorization: Bearer <access_token>
```

`admin` can manage cameras, watchlist records, and bulk onboarding. `operator` can view operational data, ingest analytics, acknowledge/resolve alerts, and send heartbeats.

External edge/analytics services may submit `POST /api/v1/events` with `X-Analytics-Key: <configured-key>` instead of a user session. The key is optional and disabled when `ANALYTICS_API_KEY` is unset; reads and simulator actions still require a logged-in user.

## Common error shape

```json
{"detail":"Human-readable validation or authorization message"}
```

Validation errors use FastAPI’s structured `detail` array. Authentication returns `401`, role failures return `403`, missing resources return `404`, duplicate IDs return `409`, and rate limits return `429`.

## GIS tile configuration

Authenticated dashboards can read the active public map settings from `GET /api/v1/system/map-config`. The response contains `tile_url`, `attribution`, `max_zoom`, and `referrer_policy`; it does not contain private provider credentials. The development default uses the exact OpenStreetMap Standard URL with visible attribution. Deployments with meaningful traffic should set `MAP_TILE_URL` and `MAP_ATTRIBUTION` to an approved or self-hosted provider and follow its terms.

## Camera payloads

`POST /api/v1/cameras` and `POST /api/v1/cameras/onboard` accept:

```json
{
  "camera_id":"C201",
  "name":"New junction",
  "department":"City Police",
  "latitude":23.02,
  "longitude":72.57,
  "camera_type":"ANPR_FIXED",
  "source_protocol":"RTSP",
  "stream_endpoint":"sim://rtsp/site/c201",
  "status":"ONLINE",
  "zone":"West Ahmedabad",
  "storage_provider":"Regional object store",
  "storage_bucket":"cctv-west-hot",
  "storage_retention_days":15
}
```

Bulk onboarding uses `{"cameras":[CameraCreate, ...]}` and returns created/skipped IDs. Stream references may use `sim://`, `vault://`, `rtsp://`, `rtsps://`, `onvif://`, `hls://`, `http://`, or `https://`; user-info and credential/signature query parameters such as `password`, `token`, `apikey`, and `signature` are rejected. Export is available at `/api/v1/cameras/export.csv`. Gap analysis reports expected-zone coverage, status counts, and ageing cameras.

## Event ingestion

`POST /api/v1/events` returns HTTP `202` with:

```json
{
  "event": {"id": 42, "event_key":"edge-key", "entity_identifier":"GJ01AB1234"},
  "alert": {"id":"uuid", "severity":"CRITICAL", "status":"OPEN"},
  "duplicate": false
}
```

The API accepts `vehicle_number` as a compatibility alias for `entity_identifier`. It validates the camera exists, confidence is between 0 and 1, timestamps are valid, and the event key is bounded. When `entity_type` is omitted, it is inferred only for recognized vehicle, person, or object event types; unknown detections remain unclassified rather than being treated as people. Repeated idempotency keys return the original persisted event.

## Search and route reconstruction

- `GET /api/v1/events?q=GJ01AB1234` searches entity identifier, camera ID, and event type.
- `GET /api/v1/events?entity_identifier=GJ01AB1234` applies the exact normalized identifier filter.
- `GET /api/v1/events/entities/GJ01AB1234/history`
- `GET /api/v1/watchlist?q=GJ01AB1234`
- `GET /api/v1/cameras?q=Ahmedabad&status=ONLINE&protocol=RTSP`

The history response includes chronological points, camera metadata, alert IDs/severity, and a Leaflet-ready `route` array.

## Alerts

- `GET /api/v1/alerts?status=OPEN&severity=CRITICAL`
- `POST /api/v1/alerts/{alert_id}/acknowledge`
- `POST /api/v1/alerts/{alert_id}/resolve`

Camera responses include `active_alert_count` and `highest_alert_severity` so GIS clients can distinguish operational health from active alert state. The alert stores timestamp, camera, coordinates, zone, matched identifier, confidence, severity, status, and operator audit fields.

## Realtime

Connect to `WS /ws` with the session cookie. The server sends a `connected` message, then JSON messages such as:

```json
{"type":"detection","event":{"entity_identifier":"GJ01AB1234"},"alert":{"id":"..."}}
{"type":"alert.updated","alert":{"status":"ACKNOWLEDGED"}}
{"type":"camera.health","camera":{"camera_id":"C006","status":"ONLINE"}}
```

`GET /api/v1/realtime/stream` provides an SSE equivalent for clients that cannot maintain a WebSocket.

## Simulation endpoints

The simulator is intentionally explicit and auditable:

- `POST /api/v1/events/simulator/emit` accepts an optional camera, identifier, and `entity_type` (`VEHICLE`, `PERSON`, or `OBJECT`).
- `POST /api/v1/events/simulator/tick` emits one event from an enabled camera.

Set `SIMULATOR_ENABLED=false` outside demonstrations.
