# Assignment Compliance Checklist

## Product and end-to-end flow

- [x] Manual camera onboarding.
- [x] API-based camera onboarding and bulk JSON onboarding.
- [x] Camera metadata, location, protocol, health, zone, and storage fields.
- [x] Search, filters, export, status history, and audit history.
- [x] Leaflet map markers and route reconstruction with configurable tile provider, visible attribution, and policy-safe referrer behavior.
- [x] RTSP and ONVIF adapter classes with near-live feed output.
- [x] Unified dashboard with health counts, live grid, alerts, detections, activity, and statistics.
- [x] Validated analytics event API with ANPR example, idempotency, and optional service-key ingestion.
- [x] Synthetic watchlist records and normalized correlation.
- [x] Alert timestamp, camera, location, entity, confidence, severity, status, acknowledgement, and resolution.
- [x] WebSocket and SSE real-time synchronization.
- [x] Entity search, chronological history, and GIS route.

## Production thinking

- [x] Adapter/plugin boundary for RTSP, ONVIF, vendor APIs, HLS, and WebRTC.
- [x] PostgreSQL/PostGIS production schema baseline with spatial, foreign-key, and time indexes.
- [x] Edge/regional/central scale strategy and 80,000-camera roadmap.
- [x] GPU, bandwidth, storage, queue, caching, load balancing, observability, HA, and DR notes.
- [x] Indicative pilot and statewide cost estimates, assumptions, and benefit model.
- [x] Security, RBAC, validation, rate limiting, audit, environment configuration, and TLS deployment guidance.

## Submission artifacts

- [x] README setup and architecture guide.
- [x] Architecture diagram and HLD.
- [x] OpenAPI/Swagger endpoint and API notes.
- [x] SQL schema and ER diagram.
- [x] Representative 50-camera CSV and watchlist JSON.
- [x] Automated tests.
- [x] 3–5 minute screen-recording runbook.
- [ ] Actual screen-recorded video file, because recording requires a running browser session and a candidate-owned hosting link.
- [ ] Government-provided feed credentials and output report, because they are not included in the assignment PDF repository.

The two unchecked items are external submission artifacts rather than missing prototype implementation.
