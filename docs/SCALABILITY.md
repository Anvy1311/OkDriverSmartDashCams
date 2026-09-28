# Scalability and Deployment Note

## Target

The official scenario describes a path toward approximately 80,000 heterogeneous cameras. The prototype does not attempt to stream or model all cameras centrally. The scale strategy is edge-first, metadata-first, and event-driven.

## Reference sizing assumptions

Use these assumptions for initial planning and replace them with measured departmental data:

- 80,000 cameras across 8 regional domains.
- 10% of cameras viewed concurrently by operators: 8,000 active sessions.
- 1–4 Mbps per active H.264/H.265 view before adaptive transcoding; WebRTC can be higher.
- 15 days hot metadata/event retention, 30–90 days warm archive, and policy-driven cold retention.
- 1–5 million analytics events per day after deduplication, with a much smaller alert-match rate.
- One active operator shift per region with a 2:1 operational viewing to camera ratio.

Actual sizing must use codec, resolution, frame rate, motion, viewing behavior, and departmental retention policy.

## Topology

### Edge sites

Run protocol adapters, heartbeat collection, optional ANPR/object inference, short-lived buffering, and bandwidth shaping. Edge sites continue correlation events during WAN interruption. A low-bandwidth mode sends metadata and thumbnails instead of full video.

### Regional gateways

Terminate vendor protocols, normalize streams, run WebRTC/HLS sessions, enforce per-session bandwidth, and publish health. Regional gateways are stateless horizontally and can be replaced without changing the central registry.

### Central platform

Use load-balanced API replicas, a message bus, stateless correlation workers, PostgreSQL/PostGIS, Redis for short-lived presence/cache, object storage for evidence/recordings, and a realtime fan-out service. Never put raw video in the event database unless retention policy explicitly requires it.

## Database and event scale

- The production PostgreSQL/PostGIS baseline is [`sql/postgres_postgis.sql`](../sql/postgres_postgis.sql); adapt it with versioned migrations before applying changes.
- Partition `analytics_events` and `audit_logs` by time.
- Index `(entity_identifier, occurred_at)`, `(camera_id, occurred_at)`, and alert `(status, severity, created_at)`.
- Use PostGIS `geography(Point, 4326)` with a GiST index for radius and viewport queries.
- Use read replicas for reporting and a warehouse/search index for long-term event exploration.
- Use an outbox table and idempotent consumers so a committed event cannot be lost when realtime delivery fails.
- Apply retention/deletion jobs and legal holds at storage-policy boundaries.

## Compute and GPU

Video decoding and inference are the dominant edge/regional workloads. Start with a GPU-accelerated worker pool per region for ANPR and object detection, then autoscale on queue depth, GPU utilization, and event latency. Use CPU-only workers for metadata APIs, heartbeats, and alert actions. Benchmark actual model precision and frame rates before purchasing hardware; ANPR accuracy is more important than raw throughput.

## Bandwidth strategy

1. Never require every camera to stream continuously to the central platform.
2. Use motion/event-triggered upload and edge metadata-first operation.
3. Prefer adaptive HLS for review and WebRTC for low-latency command views.
4. Apply per-user and per-department concurrency limits, transcoding profiles, and regional CDN/cache policies.
5. Record bandwidth and dropped-frame metrics per gateway.

## Storage strategy

- **Hot:** 7–15 days of active evidence, low-latency object storage, lifecycle policy.
- **Warm:** 30–90 days of indexed recordings and event attachments, replicated object storage.
- **Cold:** policy/legally approved long-term archive, lower-cost storage with retrieval workflow.

Store only thumbnails, event clips, and metadata required for the operational use case. Apply checksum, encryption, retention, and deletion policies at ingestion.

## Availability and disaster recovery

Run the control plane across multiple availability zones with a managed PostgreSQL primary/replica setup, point-in-time recovery, queue replication, and immutable backups. Regional gateways buffer events during central failure. Rehearse metadata restore, queue replay, credential rotation, and regional failover. A practical initial target is RPO <= 15 minutes and RTO <= 2 hours, subject to department requirements.

## Indicative operating bands

These are planning bands, not quotations:

| Scale item | Small pilot | Regional pilot | Statewide target |
| --- | ---: | ---: | ---: |
| API replicas | 2 | 4–8 per region | 20+ autoscaled |
| Gateways | 1–2 | 4–12 per region | 30+ regional/edge |
| Analytics workers | 2–4 CPU/GPU | 10–40 GPU workers | autoscale by queue/GPU |
| Database | managed single node | HA primary/replica | multi-AZ/partitioned |
| Event retention | 15 days | 30–90 days | policy-driven tiers |

Cloud cost is dominated by active video sessions, recording retention, GPU-hours, WAN bandwidth, and backup storage. A low-bandwidth metadata-first design is usually the highest-leverage cost control. Indicative pilot and statewide estimates are in [`docs/COST_BENEFIT.md`](COST_BENEFIT.md).

## Rollout

1. Inventory and risk-rank one department’s 50–100 cameras.
2. Validate protocol access, ownership, location, retention, and legal feed-sharing approval.
3. Deploy one regional gateway and onboard the sample 50-camera dataset.
4. Run a designated-vehicle trace and measure event-to-alert latency.
5. Add GPU inference, HA database, queue, and observability after workflow validation.
6. Repeat by region, then integrate approved VAHAN/SARTHI/eGujCop/AFIS/NAFIS data sources through governed adapters.
