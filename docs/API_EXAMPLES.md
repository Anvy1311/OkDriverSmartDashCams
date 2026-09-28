# API Contract Examples

## Login

```bash
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"ChangeMe123!"}'
```

## List cameras

```bash
curl -b cookies.txt 'http://localhost:8000/api/v1/cameras?status=ONLINE&protocol=RTSP'
```

## Onboard a camera

```bash
curl -b cookies.txt -X POST http://localhost:8000/api/v1/cameras \
  -H 'Content-Type: application/json' \
  -d '{"camera_id":"C201","name":"Demo camera","department":"City Police","latitude":23.02,"longitude":72.57,"camera_type":"ANPR_FIXED","source_protocol":"RTSP","stream_endpoint":"sim://rtsp/demo/c201","zone":"West Ahmedabad"}'
```

## Send an event

```bash
curl -b cookies.txt -X POST http://localhost:8000/api/v1/events \
  -H 'Content-Type: application/json' \
  -d '{"camera_id":"C201","event_type":"ANPR","vehicle_number":"GJ01AB1234","confidence":0.98,"idempotency_key":"demo-c201-1"}'
```

## Service-to-service event ingestion

When `ANALYTICS_API_KEY` is configured, an edge worker can omit the session cookie:

```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H 'Content-Type: application/json' \
  -H 'X-Analytics-Key: <configured-key>' \
  -d '{"camera_id":"C001","event_type":"ANPR","entity_identifier":"GJ01AB1234","confidence":0.98,"idempotency_key":"edge-c001-service-1"}'
```

## Trace an entity

```bash
curl -b cookies.txt http://localhost:8000/api/v1/events/entities/GJ01AB1234/history
```

## Acknowledge and resolve

```bash
curl -b cookies.txt -X POST http://localhost:8000/api/v1/alerts/<alert-id>/acknowledge
curl -b cookies.txt -X POST http://localhost:8000/api/v1/alerts/<alert-id>/resolve
```

## WebSocket

Use a WebSocket client with the session cookie or send a bearer token as a query parameter only in a controlled development environment:

```text
ws://localhost:8000/ws
```
