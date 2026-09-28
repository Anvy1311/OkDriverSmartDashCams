# Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ AUDIT_LOGS : performs
    USERS ||--o{ CAMERAS : administers
    USERS ||--o{ ALERTS : acknowledges
    USERS ||--o{ ALERTS : resolves
    CAMERAS ||--o{ CAMERA_STATUS_HISTORY : records
    CAMERAS ||--o{ ANALYTICS_EVENTS : observes
    WATCHLIST_ENTRIES ||--o{ ALERTS : matches
    ANALYTICS_EVENTS ||--o| ALERTS : produces

    USERS {
        int id PK
        string username UK
        string role
        boolean is_active
    }
    CAMERAS {
        int id PK
        string camera_id UK
        string department
        float latitude
        float longitude
        string source_protocol
        string status
        string zone
        string stream_endpoint
    }
    CAMERA_STATUS_HISTORY {
        int id PK
        int camera_id FK
        string status
        datetime heartbeat_at
    }
    WATCHLIST_ENTRIES {
        int id PK
        string entity_type
        string identifier
        string severity
        boolean active
    }
    ANALYTICS_EVENTS {
        int id PK
        string event_key UK
        string camera_id FK
        string entity_identifier
        datetime occurred_at
        float confidence
    }
    ALERTS {
        string id PK
        int event_id FK
        string camera_id FK
        int watchlist_entry_id FK
        string status
        string severity
        datetime created_at
    }
    AUDIT_LOGS {
        int id PK
        int actor_id FK
        string action
        string resource_type
        datetime created_at
    }
```

## Indexing rationale

- `cameras(camera_id)` provides stable source identity.
- `cameras(status, zone)` and `cameras(department, source_protocol)` support operational registry filters.
- `analytics_events(entity_identifier, occurred_at)` supports entity movement queries.
- `analytics_events(camera_id, occurred_at)` supports camera timelines and replay filtering.
- `watchlist_entries(identifier, active)` supports low-latency correlation.
- `alerts(status, severity)` supports the response queue.
- `alerts(event_id)` is unique and prevents duplicate alerts for one event.
- `audit_logs(resource_type, resource_id, created_at)` supports auditable history.

The production PostgreSQL/PostGIS baseline, including spatial types, foreign keys, and GiST/time indexes, is in [`sql/postgres_postgis.sql`](../sql/postgres_postgis.sql). Its identifiers and alert key types align with the SQLAlchemy models, and its time-oriented indexes support future event partitioning.
