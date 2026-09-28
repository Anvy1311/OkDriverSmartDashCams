# Integration Notes

## Prototype adapters

The seeded registry includes:

- `C001`, `C003`, and `C005` using the `RTSP` adapter.
- `C002`, `C004`, and `C006` using the `ONVIF` adapter.
- Optional `HLS` and `VENDOR_API` adapter classes in `app/services/adapters.py`.

The adapters render a near-live SVG frame at `/api/v1/cameras/{camera_id}/stream`. They do not claim to decode real camera media. This makes the end-to-end backend workflow demonstrable without distributing or embedding unlicensed footage.

## Real RTSP adapter

A production RTSP adapter should:

1. Accept a camera ID and resolve a vault credential reference.
2. Validate the URL and protocol against an allowlist.
3. Probe with a bounded timeout and record codec, resolution, frame rate, packet loss, and latency.
4. Create an HLS/WebRTC session through a media gateway such as MediaMTX, SRS, or a vendor gateway.
5. Return a short-lived signed playback token to the dashboard.
6. Emit a heartbeat/health event independently of analytics.
7. Close idle sessions and apply per-department concurrency limits.

Never place a password, bearer token, private key, or credential/signature query parameter in `stream_endpoint`; the registry intentionally stores a reference, not a secret. The API accepts only approved schemes and rejects URL user-info plus common credential query names.

## ONVIF adapter

Use an ONVIF client to discover or configure device identity only when the department has authorized it. Limit discovery to approved network segments. Use the device service URL and a vault reference, then test `GetCapabilities`, `GetServices`, and the configured media profile. Do not enable remote discovery or default credentials in production.

## Vendor API/SDK adapter

Implement a vendor adapter behind the same interface. Map vendor-specific camera IDs, stream URLs, event callbacks, and authentication into the normalized camera/event schemas. Keep vendor SDK dependencies isolated in a worker container so a vendor library failure cannot take down the registry or alert API.

## Browser delivery

RTSP is not a browser protocol. Use one of these production paths:

- WebRTC gateway for low-latency live viewing and two-way control-room interaction.
- HLS for browser playback, recording windows, and low-bandwidth fallback.
- A vendor-supported WebRTC/HLS gateway where direct integration is not available.

Only operators who need live video should receive a stream. Store session audit records and expire signed URLs quickly.

## Map tiles and GIS

The browser map is configured through `MAP_TILE_URL`, `MAP_ATTRIBUTION`, and `MAP_MAX_ZOOM`. The development default uses the exact OpenStreetMap Standard URL, keeps the required attribution visible, sends a cross-origin `Referer`, and allows normal browser caching. Leaflet is not given a subdomain tile URL, a cache-busting query, or a prefetch loop.

The public OSMF tile service is best-effort and intended for low-volume interactive use under its [tile usage policy](https://operations.osmfoundation.org/policies/tiles/). For a public deployment, use an approved provider or self-hosted tiles and set the corresponding attribution before serving traffic. Do not proxy or bulk-download OSM tiles, strip the `Referer`, or add offline/region prefetching. The authenticated `/api/v1/system/map-config` endpoint supplies the active public tile settings to the dashboard; tile credentials, if a chosen provider requires them, must be provider-restricted browser credentials rather than application secrets.

If the configured tile service is unavailable, the dashboard keeps camera markers and movement routes visible and shows a non-blocking tile error. This preserves operational context while the provider is corrected.

## AI event contract

The central API accepts an inference event independently of the video transport:

```json
{
  "camera_id": "C001",
  "event_type": "ANPR",
  "occurred_at": "2026-09-25T10:02:00Z",
  "entity_type": "VEHICLE",
  "entity_identifier": "GJ01AB1234",
  "confidence": 0.98,
  "vehicle_type": "CAR",
  "bounding_box": {"x": 312, "y": 248, "width": 160, "height": 72},
  "metadata": {"model": "anpr-v1", "gateway": "west-02"},
  "idempotency_key": "west-02-C001-20260925T100200-001"
}
```

The event can originate at an edge gateway, a vendor callback, a message-bus consumer, or the documented simulator. The backend does not require a model to be trained in the prototype.
