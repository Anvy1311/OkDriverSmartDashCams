from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    department: str | None = None
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class CameraBase(BaseModel):
    camera_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=180)
    department: str = Field(min_length=2, max_length=180)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    camera_type: str = Field(min_length=2, max_length=80)
    source_protocol: str = Field(min_length=2, max_length=40)
    stream_endpoint: str = Field(min_length=3, max_length=500)
    status: Literal["ONLINE", "OFFLINE", "DEGRADED"] = "ONLINE"
    last_heartbeat: datetime | None = None
    zone: str = Field(min_length=2, max_length=120)
    storage_provider: str | None = Field(default=None, max_length=120)
    storage_bucket: str | None = Field(default=None, max_length=180)
    storage_retention_days: int | None = Field(default=None, ge=1, le=3650)
    coverage_area: str | None = Field(default=None, max_length=240)
    enabled: bool = True
    extra_data: dict[str, Any] = Field(default_factory=dict)


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    department: str | None = Field(default=None, min_length=2, max_length=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    camera_type: str | None = Field(default=None, min_length=2, max_length=80)
    source_protocol: str | None = Field(default=None, min_length=2, max_length=40)
    stream_endpoint: str | None = Field(default=None, min_length=3, max_length=500)
    status: Literal["ONLINE", "OFFLINE", "DEGRADED"] | None = None
    last_heartbeat: datetime | None = None
    zone: str | None = Field(default=None, min_length=2, max_length=120)
    storage_provider: str | None = Field(default=None, max_length=120)
    storage_bucket: str | None = Field(default=None, max_length=180)
    storage_retention_days: int | None = Field(default=None, ge=1, le=3650)
    coverage_area: str | None = Field(default=None, max_length=240)
    enabled: bool | None = None
    extra_data: dict[str, Any] | None = None


class CameraOut(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    active_alert_count: int = 0
    highest_alert_severity: str | None = None


class CameraListResponse(BaseModel):
    items: list[CameraOut]
    total: int
    page: int
    page_size: int


class BulkCameraRequest(BaseModel):
    cameras: list[CameraCreate] = Field(min_length=1, max_length=5000)


class WatchlistBase(BaseModel):
    entity_type: Literal["VEHICLE", "PERSON", "OBJECT"] = "VEHICLE"
    identifier: str = Field(min_length=2, max_length=160)
    display_name: str = Field(min_length=2, max_length=180)
    reason: str = Field(min_length=2, max_length=500)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    department: str | None = Field(default=None, max_length=180)
    active: bool = True
    extra_data: dict[str, Any] = Field(default_factory=dict)


class WatchlistCreate(WatchlistBase):
    pass


class WatchlistUpdate(BaseModel):
    entity_type: Literal["VEHICLE", "PERSON", "OBJECT"] | None = None
    identifier: str | None = Field(default=None, min_length=2, max_length=160)
    display_name: str | None = Field(default=None, min_length=2, max_length=180)
    reason: str | None = Field(default=None, min_length=2, max_length=500)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    department: str | None = Field(default=None, max_length=180)
    active: bool | None = None
    extra_data: dict[str, Any] | None = None


class WatchlistOut(WatchlistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AnalyticsEventCreate(BaseModel):
    camera_id: str = Field(min_length=2, max_length=64)
    event_type: str = Field(min_length=2, max_length=64)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entity_type: Literal["VEHICLE", "PERSON", "OBJECT"] | None = None
    entity_identifier: str | None = Field(default=None, max_length=160)
    vehicle_number: str | None = Field(default=None, max_length=160)
    confidence: float | None = Field(default=None, ge=0, le=1)
    vehicle_type: str | None = Field(default=None, max_length=80)
    bounding_box: dict[str, float] | list[float] | None = None
    speed_kph: float | None = Field(default=None, ge=0, le=500)
    source: str = Field(default="api", max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=180)

    @model_validator(mode="after")
    def align_identifier_fields(self) -> "AnalyticsEventCreate":
        if (
            self.entity_identifier
            and self.vehicle_number
            and self.entity_identifier.replace(" ", "").upper() != self.vehicle_number.replace(" ", "").upper()
        ):
            raise ValueError("entity_identifier and vehicle_number must identify the same entity")
        if self.vehicle_number and not self.entity_identifier:
            self.entity_identifier = self.vehicle_number
        if self.entity_type is None and self.entity_identifier:
            event_type = self.event_type.upper()
            if event_type in {"ANPR", "VEHICLE_DETECTION", "VEHICLE"}:
                self.entity_type = "VEHICLE"
            elif event_type in {"PERSON", "PERSON_DETECTION", "FACE_MATCH", "FACE_RECOGNITION"}:
                self.entity_type = "PERSON"
            elif event_type in {"OBJECT", "OBJECT_DETECTION"}:
                self.entity_type = "OBJECT"
        return self


class AnalyticsEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_key: str
    camera_id: str
    occurred_at: datetime
    received_at: datetime
    event_type: str
    entity_type: str | None
    entity_identifier: str | None
    confidence: float | None
    vehicle_type: str | None
    bounding_box: dict[str, float] | list[float] | None
    speed_kph: float | None
    source: str
    extra_data: dict[str, Any]
    alert_id: str | None = None


class EventIngestResponse(BaseModel):
    event: AnalyticsEventOut
    alert: dict[str, Any] | None = None
    duplicate: bool = False


class EventListResponse(BaseModel):
    items: list[AnalyticsEventOut]
    total: int
    page: int
    page_size: int


class AlertOut(BaseModel):
    id: str
    event_id: int
    camera_id: str
    watchlist_entry_id: int
    severity: str
    status: str
    message: str
    matched_identifier: str
    confidence: float | None
    latitude: float | None
    longitude: float | None
    zone: str | None
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    acknowledged_by: str | None
    resolved_by: str | None
    camera_name: str | None = None
    entity_name: str | None = None


class AlertListResponse(BaseModel):
    items: list[AlertOut]
    total: int
    page: int
    page_size: int


class EntityHistoryPoint(BaseModel):
    event_id: int
    camera_id: str
    camera_name: str
    department: str
    latitude: float
    longitude: float
    zone: str
    occurred_at: datetime
    event_type: str
    confidence: float | None
    alert_id: str | None = None
    severity: str | None = None


class EntityHistoryResponse(BaseModel):
    identifier: str
    entity_type: str | None
    total: int
    points: list[EntityHistoryPoint]
    route: list[list[float]]


class DashboardStats(BaseModel):
    total_cameras: int
    online_cameras: int
    offline_cameras: int
    degraded_cameras: int
    disabled_cameras: int
    total_events: int
    events_today: int
    open_alerts: int
    critical_alerts: int
    watchlist_entries: int
    active_sources: int
    last_event_at: datetime | None
    last_alert_at: datetime | None


class SimulatorRequest(BaseModel):
    camera_id: str | None = Field(default=None, max_length=64)
    event_type: str = Field(default="ANPR", min_length=2, max_length=64)
    entity_type: Literal["VEHICLE", "PERSON", "OBJECT"] | None = None
    entity_identifier: str | None = Field(default=None, max_length=160)
    confidence: float = Field(default=0.96, ge=0, le=1)
    vehicle_type: str = Field(default="CAR", max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=180)


class GapAnalysisResponse(BaseModel):
    total_zones: int
    covered_zones: int
    uncovered_zones: list[str]
    cameras_by_status: dict[str, int]
    aging_camera_count: int
    generated_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict[str, Any]
    created_at: datetime
