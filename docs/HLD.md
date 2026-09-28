# High-Level Design

## Proposed model

Use a hybrid architecture with **Model 1 Registry/GIS as the mandatory foundation**, **Model 2 unified viewing**, **Model 3 adapter federation**, and a **Model 4-style central analytics and alert plane**. Existing department VMS systems remain owners of their cameras and recordings. The central platform stores normalized metadata and selected analytics, not every raw stream by default.

## Functional requirements mapped to components

| Requirement | Design response |
| --- | --- |
| Heterogeneous onboarding | Versioned camera schema, protocol adapter registry, manual/API/bulk onboarding, validation and audit |
| Asset visibility | Camera registry, department/protocol/status/zone filters, CSV export, PostGIS-ready coordinates |
| Health | Authenticated heartbeat endpoint, simulator-only probe worker for `sim://` sources, status history, online/degraded/offline UI states, realtime health events |
| Unified viewing | Adapter gateway boundary, browser session contract, HLS/WebRTC production target |
| Metadata analytics | Validated event API, immutable event store, entity/time indexes, route reconstruction |
| Watchlist correlation | Active record service, normalized identifier index, confidence and severity, one alert per event |
| Response | WebSocket/SSE push, alert acknowledgement/resolution, audit trail |
| Scale | Edge/regional/central tiers, queue fan-out, horizontal workers, object storage tiers |
| Security | RBAC, vault-backed stream credentials, TLS termination, audit, rate limits, segmentation |

## Logical services

### Registry service

Owns `cameras`, status history, ownership, storage references, location, and lifecycle actions. It publishes `camera.created`, `camera.updated`, and `camera.health` events. A production implementation should expose a versioned schema and migration pipeline.

### Federation gateway

Runs at regional or edge locations. It translates RTSP, ONVIF, vendor APIs, and SDKs into a common session and health contract. It must not expose vendor credentials to the browser or central database.

### Analytics plane

Receives inference events from edge or central workers. It validates source identity, timestamp, confidence, and event type, stores the event, performs watchlist lookup, and publishes a normalized alert. AI model training is out of scope; model serving and event contracts are in scope.

### Operations plane

Serves the dashboard, GIS, event search, route reconstruction, alert workflow, role-aware views, and exports. It is stateless in production and obtains authorization from the identity service.

## Data ownership

- Registry: camera metadata and current health.
- Gateway: transient sessions, connection health, and signed playback references.
- Analytics: inference metadata and model version.
- Correlation: watchlist versions, match decisions, and alert lifecycle.
- Audit: append-only action history.
- Storage: recording segments and evidence objects with retention policies.

## Deployment topology

```text
Camera sites
   |
Regional edge gateways (RTSP/ONVIF/vendor adapters, heartbeat, optional inference)
   |
Regional ingest/API replicas -- Redis/NATS/Kafka -- correlation workers
   |                                      |
PostgreSQL + PostGIS        Object storage / archive       Observability
   |
Load-balanced API and WebSocket/SSE fan-out
   |
Command-center dashboard and approved integrations
```

## Availability and recovery

Run at least two API replicas per region behind a load balancer. Use a multi-AZ database with point-in-time recovery, replicated object storage, and a queue with dead-letter handling. Regional gateways continue event buffering during central connectivity loss. Disaster recovery objectives should be agreed with the department; a starting target is RPO under 15 minutes for metadata and RTO under 2 hours for the command plane.

## Department onboarding information

For each department, collect camera ID, ownership, physical location, coverage, camera/VMS make and model, supported protocols, codec/profile, bandwidth, retention, ownership, access windows, contact/maintenance owner, and authorization to share the feed. Record integration readiness and unresolved gaps in the registry rather than hiding them in a spreadsheet.
