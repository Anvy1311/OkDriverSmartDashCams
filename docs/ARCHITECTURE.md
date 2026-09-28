# Architecture

## Scope

The prototype is a hybrid of the hackathon’s registry, unified viewing, federation, and central analytics ideas. The registry is the source of truth for camera identity and location. Adapters isolate vendor/protocol differences. Analytics events are the integration contract between video/AI processing and operational alerting. The dashboard is a consumer of the same API and realtime channel.

## Components

| Component | Prototype implementation | Production seam |
| --- | --- | --- |
| Registry | SQLAlchemy `cameras`, `camera_status_history` | PostgreSQL/PostGIS registry service |
| Feed access | `app/services/adapters.py` RTSP and ONVIF simulators | RTSP/ONVIF/vendor SDK gateway with credential vault |
| Event ingestion | `POST /api/v1/events` | Kafka/RabbitMQ ingress plus HTTP bridge |
| Correlation | `app/services/analytics_service.py` | Dedicated low-latency correlation workers |
| Persistence | SQLite by default | PostgreSQL, object storage, time-series/event partitions |
| Realtime | In-process WebSocket/SSE manager | Redis/NATS/Kafka fan-out and regional gateways |
| Dashboard | Static responsive console in `static/` | React/Vue/Next shell using the same REST/OpenAPI contract |
| GIS | Leaflet with configurable public tile settings | Leaflet/OpenLayers with PostGIS spatial queries and an approved/self-hosted tile provider |
| Audit | `audit_logs` | Append-only centralized audit store |

## End-to-end flow

1. An administrator submits a camera through the manual form, `POST /api/v1/cameras/onboard`, or `POST /api/v1/cameras/bulk`.
2. The registry validates coordinates, protocol, status, and a secret-free endpoint reference. A camera audit record is written in the same transaction.
3. A heartbeat or adapter probe updates health and status history. The dashboard receives a `camera.health` message over WebSocket/SSE.
4. An edge analytics worker or operator simulator submits an inference result. The API validates the schema and source camera, then computes or accepts an idempotency key.
5. The event and normalized identifier are stored. Active watchlist records are compared using a case- and whitespace-normalized index.
6. A match creates one alert tied one-to-one to the event. The transaction commits before the realtime broadcast.
7. The dashboard displays the event and alert without a refresh. Operators acknowledge or resolve the alert; each transition is audited and broadcast.
8. Entity history queries the event index in timestamp order and returns a route as `[longitude, latitude]` pairs.

## Adapter contract

An adapter receives a camera record and exposes a normalized feed/session result. The current simulator implements the same boundary for RTSP, ONVIF, HLS, and vendor API protocols. A real adapter should:

- resolve a credential reference through a vault rather than storing credentials in `cameras`;
- negotiate protocol, codec, resolution, and latency policy;
- return a WebRTC session, HLS manifest, or a signed gateway URL;
- emit a health signal independently of analytics events;
- avoid placing raw video in the event API;
- include source, camera, timestamp, and confidence metadata in every event.

## Consistency and failure behavior

- `event_key` and `alerts.event_id` are unique constraints. Retries return `duplicate: true` and do not create another alert.
- Event and alert rows commit together. A realtime message is sent only after commit.
- In-process realtime delivery is best effort. The persisted event remains queryable if a browser disconnects.
- A production broker should use an outbox table or transactional consumer to guarantee replay after process failure.
- SQLite serializes writes for the prototype. PostgreSQL row-level locking, partitions, and a queue are required for multi-worker scale.

## Observability

Every request carries a duration header. Health endpoints verify the database. The background jobs log failures through the application logger. Production should add structured JSON logs, request IDs, Prometheus metrics for event latency/queue depth/camera health, distributed tracing, and alerting on heartbeat gaps.
