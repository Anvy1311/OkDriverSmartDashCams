PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(120) NOT NULL UNIQUE,
    display_name VARCHAR(160) NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'operator',
    department VARCHAR(160),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS cameras (
    id INTEGER PRIMARY KEY,
    camera_id VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(180) NOT NULL,
    department VARCHAR(180) NOT NULL,
    latitude DOUBLE NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    camera_type VARCHAR(80) NOT NULL,
    source_protocol VARCHAR(40) NOT NULL,
    stream_endpoint VARCHAR(500) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'ONLINE' CHECK (status IN ('ONLINE', 'OFFLINE', 'DEGRADED')),
    last_heartbeat TIMESTAMP,
    zone VARCHAR(120) NOT NULL,
    storage_provider VARCHAR(120),
    storage_bucket VARCHAR(180),
    storage_retention_days INTEGER CHECK (storage_retention_days BETWEEN 1 AND 3650),
    coverage_area VARCHAR(240),
    enabled BOOLEAN NOT NULL DEFAULT 1,
    extra_data JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cameras_status_zone ON cameras(status, zone);
CREATE INDEX IF NOT EXISTS ix_cameras_department_protocol ON cameras(department, source_protocol);
CREATE INDEX IF NOT EXISTS ix_cameras_camera_id ON cameras(camera_id);
CREATE INDEX IF NOT EXISTS ix_cameras_zone ON cameras(zone);
CREATE INDEX IF NOT EXISTS ix_cameras_source_protocol ON cameras(source_protocol);
CREATE INDEX IF NOT EXISTS ix_cameras_enabled ON cameras(enabled);

CREATE TABLE IF NOT EXISTS camera_status_history (
    id INTEGER PRIMARY KEY,
    camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    status VARCHAR(24) NOT NULL,
    heartbeat_at TIMESTAMP NOT NULL,
    reason VARCHAR(240)
);

CREATE INDEX IF NOT EXISTS ix_camera_status_history_camera ON camera_status_history(camera_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    resource_id VARCHAR(100),
    details JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at);

CREATE TABLE IF NOT EXISTS watchlist_entries (
    id INTEGER PRIMARY KEY,
    entity_type VARCHAR(32) NOT NULL,
    identifier VARCHAR(160) NOT NULL,
    display_name VARCHAR(180) NOT NULL,
    reason VARCHAR(500) NOT NULL,
    severity VARCHAR(24) NOT NULL DEFAULT 'HIGH' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    department VARCHAR(180),
    active BOOLEAN NOT NULL DEFAULT 1,
    extra_data JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_watchlist_identifier_active ON watchlist_entries(identifier, active);
CREATE INDEX IF NOT EXISTS ix_watchlist_entity_type ON watchlist_entries(entity_type);

CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY,
    event_key VARCHAR(180) NOT NULL UNIQUE,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    occurred_at TIMESTAMP NOT NULL,
    received_at TIMESTAMP NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32),
    entity_identifier VARCHAR(160),
    confidence DOUBLE CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    vehicle_type VARCHAR(80),
    bounding_box JSON,
    speed_kph DOUBLE,
    extra_data JSON NOT NULL DEFAULT '{}',
    source VARCHAR(80) NOT NULL DEFAULT 'api'
);

CREATE INDEX IF NOT EXISTS ix_events_entity_occurred ON analytics_events(entity_identifier, occurred_at);
CREATE INDEX IF NOT EXISTS ix_events_camera_occurred ON analytics_events(camera_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_events_event_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS ix_events_received_at ON analytics_events(received_at);

CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(36) PRIMARY KEY,
    event_id INTEGER NOT NULL UNIQUE REFERENCES analytics_events(id) ON DELETE CASCADE,
    camera_id VARCHAR(64) NOT NULL REFERENCES cameras(camera_id) ON DELETE CASCADE,
    watchlist_entry_id INTEGER NOT NULL REFERENCES watchlist_entries(id),
    severity VARCHAR(24) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status VARCHAR(24) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
    message VARCHAR(600) NOT NULL,
    matched_identifier VARCHAR(160) NOT NULL,
    confidence DOUBLE,
    latitude DOUBLE,
    longitude DOUBLE,
    zone VARCHAR(120),
    created_at TIMESTAMP NOT NULL,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    acknowledged_by VARCHAR(120),
    resolved_by VARCHAR(120)
);

CREATE INDEX IF NOT EXISTS ix_alerts_status_severity ON alerts(status, severity);
CREATE INDEX IF NOT EXISTS ix_alerts_created_camera ON alerts(created_at, camera_id);
CREATE INDEX IF NOT EXISTS ix_alerts_matched_identifier ON alerts(matched_identifier);
