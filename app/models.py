from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), default="operator", index=True)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (
        Index("ix_cameras_status_zone", "status", "zone"),
        Index("ix_cameras_department_protocol", "department", "source_protocol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    department: Mapped[str] = mapped_column(String(180), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    camera_type: Mapped[str] = mapped_column(String(80))
    source_protocol: Mapped[str] = mapped_column(String(40), index=True)
    stream_endpoint: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="ONLINE", index=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    zone: Mapped[str] = mapped_column(String(120), index=True)
    storage_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(180), nullable=True)
    storage_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coverage_area: Mapped[str | None] = mapped_column(String(240), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class CameraStatusHistory(Base):
    __tablename__ = "camera_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), index=True)
    status: Mapped[str] = mapped_column(String(24))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reason: Mapped[str | None] = mapped_column(String(240), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"
    __table_args__ = (Index("ix_watchlist_identifier_active", "identifier", "active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    identifier: Mapped[str] = mapped_column(String(160), index=True)
    display_name: Mapped[str] = mapped_column(String(180))
    reason: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(24), default="HIGH", index=True)
    department: Mapped[str | None] = mapped_column(String(180), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_events_entity_occurred", "entity_identifier", "occurred_at"),
        Index("ix_events_camera_occurred", "camera_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.camera_id", ondelete="CASCADE"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    entity_identifier: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bounding_box: Mapped[dict[str, float] | list[float] | None] = mapped_column(JSON, nullable=True)
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(80), default="api")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_created_camera", "created_at", "camera_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("analytics_events.id"), unique=True, index=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.camera_id", ondelete="CASCADE"), index=True)
    watchlist_entry_id: Mapped[int] = mapped_column(ForeignKey("watchlist_entries.id"), index=True)
    severity: Mapped[str] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(24), default="OPEN", index=True)
    message: Mapped[str] = mapped_column(String(600))
    matched_identifier: Mapped[str] = mapped_column(String(160), index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    zone: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
