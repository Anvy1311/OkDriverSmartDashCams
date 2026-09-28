import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Alert, AnalyticsEvent, Camera, WatchlistEntry
from ..schemas import AnalyticsEventCreate
from .audit import record_audit


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_identifier(identifier: str) -> str:
    return "".join(identifier.split()).upper()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def make_event_key(payload: AnalyticsEventCreate, camera: Camera) -> str:
    if payload.idempotency_key:
        return payload.idempotency_key
    basis = {
        "camera_id": camera.camera_id,
        "occurred_at": payload.occurred_at.isoformat(),
        "event_type": payload.event_type.upper(),
        "entity_identifier": normalize_identifier(payload.entity_identifier or ""),
        "confidence": payload.confidence,
    }
    return "auto-" + hashlib.sha256(json.dumps(basis, sort_keys=True).encode("utf-8")).hexdigest()[:32]


def event_to_dict(event: AnalyticsEvent, alert: Alert | None = None) -> dict[str, Any]:
    if alert is None:
        alert = getattr(event, "alert", None)
    return {
        "id": event.id,
        "event_key": event.event_key,
        "camera_id": event.camera_id,
        "occurred_at": event.occurred_at,
        "received_at": event.received_at,
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_identifier": event.entity_identifier,
        "confidence": event.confidence,
        "vehicle_type": event.vehicle_type,
        "bounding_box": event.bounding_box,
        "speed_kph": event.speed_kph,
        "source": event.source,
        "extra_data": event.extra_data or {},
        "alert_id": alert.id if alert else None,
    }


def alert_to_dict(alert: Alert, camera: Camera | None = None, entry: WatchlistEntry | None = None) -> dict[str, Any]:
    return {
        "id": alert.id,
        "event_id": alert.event_id,
        "camera_id": alert.camera_id,
        "watchlist_entry_id": alert.watchlist_entry_id,
        "severity": alert.severity,
        "status": alert.status,
        "message": alert.message,
        "matched_identifier": alert.matched_identifier,
        "confidence": alert.confidence,
        "latitude": alert.latitude,
        "longitude": alert.longitude,
        "zone": alert.zone,
        "created_at": alert.created_at,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "acknowledged_by": alert.acknowledged_by,
        "resolved_by": alert.resolved_by,
        "camera_name": camera.name if camera else None,
        "entity_name": entry.display_name if entry else None,
    }


def camera_alert_state(db: Session, camera_id: str) -> tuple[int, str | None]:
    severities = db.scalars(
        select(Alert.severity).where(
            Alert.camera_id == camera_id,
            Alert.status.in_(["OPEN", "ACKNOWLEDGED"]),
        )
    ).all()
    priority = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    highest = max(severities, key=lambda severity: priority.get(severity, 0), default=None)
    return len(severities), highest


def find_watchlist_match(db: Session, entity_type: str | None, identifier: str | None) -> WatchlistEntry | None:
    if not identifier:
        return None
    normalized = normalize_identifier(identifier)
    query = select(WatchlistEntry).where(
        WatchlistEntry.active.is_(True),
        func.upper(func.replace(WatchlistEntry.identifier, " ", "")) == normalized,
    )
    if entity_type:
        query = query.where(WatchlistEntry.entity_type == entity_type)
    return db.scalar(query)


def _existing_event(db: Session, event_key: str) -> tuple[AnalyticsEvent, Alert | None] | None:
    event = db.scalar(select(AnalyticsEvent).where(AnalyticsEvent.event_key == event_key))
    if not event:
        return None
    alert = db.scalar(select(Alert).where(Alert.event_id == event.id))
    return event, alert


def ingest_event(
    db: Session,
    payload: AnalyticsEventCreate,
    actor_id: int | None = None,
) -> tuple[AnalyticsEvent, Alert | None, bool]:
    camera = db.scalar(select(Camera).where(Camera.camera_id == payload.camera_id))
    if not camera:
        raise ValueError(f"Camera '{payload.camera_id}' is not registered")
    if not camera.enabled:
        raise ValueError(f"Camera '{payload.camera_id}' is disabled")
    occurred_at = ensure_utc(payload.occurred_at)
    normalized_payload = payload.model_copy(update={"occurred_at": occurred_at})
    if normalized_payload.entity_identifier:
        normalized_payload.entity_identifier = normalize_identifier(normalized_payload.entity_identifier)
    event_key = make_event_key(normalized_payload, camera)
    existing = _existing_event(db, event_key)
    if existing:
        return existing[0], existing[1], True

    identifier = normalized_payload.entity_identifier
    match = find_watchlist_match(db, normalized_payload.entity_type, identifier)
    event = AnalyticsEvent(
        event_key=event_key,
        camera_id=camera.camera_id,
        occurred_at=occurred_at,
        event_type=normalized_payload.event_type.upper(),
        entity_type=normalized_payload.entity_type,
        entity_identifier=identifier,
        confidence=normalized_payload.confidence,
        vehicle_type=normalized_payload.vehicle_type,
        bounding_box=normalized_payload.bounding_box,
        speed_kph=normalized_payload.speed_kph,
        extra_data=normalized_payload.metadata,
        source=normalized_payload.source,
    )
    db.add(event)
    try:
        db.flush()
        alert: Alert | None = None
        if match and identifier:
            alert = Alert(
                id=str(uuid.uuid4()),
                event_id=event.id,
                camera_id=camera.camera_id,
                watchlist_entry_id=match.id,
                severity=match.severity,
                status="OPEN",
                message=f"{match.display_name} matched {identifier} at {camera.name}",
                matched_identifier=identifier,
                confidence=normalized_payload.confidence,
                latitude=camera.latitude,
                longitude=camera.longitude,
                zone=camera.zone,
            )
            db.add(alert)
            record_audit(
                db,
                action="alert.created",
                resource_type="alert",
                resource_id=alert.id,
                actor_id=actor_id,
                details={
                    "camera_id": camera.camera_id,
                    "event_id": event.id,
                    "matched_identifier": identifier,
                    "severity": match.severity,
                },
            )
        record_audit(
            db,
            action="analytics.event.received",
            resource_type="analytics_event",
            resource_id=event.id,
            actor_id=actor_id,
            details={
                "camera_id": camera.camera_id,
                "event_type": event.event_type,
                "entity_identifier": identifier,
                "alert_generated": bool(alert),
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing_event(db, event_key)
        if existing:
            return existing[0], existing[1], True
        raise
    db.refresh(event)
    if alert:
        db.refresh(alert)
    return event, alert, False


def list_history(db: Session, identifier: str) -> dict[str, Any]:
    normalized = normalize_identifier(identifier)
    rows = db.execute(
        select(AnalyticsEvent, Camera, Alert)
        .join(Camera, Camera.camera_id == AnalyticsEvent.camera_id)
        .outerjoin(Alert, Alert.event_id == AnalyticsEvent.id)
        .where(func.upper(func.replace(AnalyticsEvent.entity_identifier, " ", "")) == normalized)
        .order_by(AnalyticsEvent.occurred_at.asc())
    ).all()
    points: list[dict[str, Any]] = []
    for event, camera, alert in rows:
        points.append(
            {
                "event_id": event.id,
                "camera_id": camera.camera_id,
                "camera_name": camera.name,
                "department": camera.department,
                "latitude": camera.latitude,
                "longitude": camera.longitude,
                "zone": camera.zone,
                "occurred_at": event.occurred_at,
                "event_type": event.event_type,
                "confidence": event.confidence,
                "alert_id": alert.id if alert else None,
                "severity": alert.severity if alert else None,
            }
        )
    return {
        "identifier": identifier,
        "entity_type": rows[0][0].entity_type if rows else None,
        "total": len(points),
        "points": points,
        "route": [[point["longitude"], point["latitude"]] for point in points],
    }


def get_dashboard_stats(db: Session) -> dict[str, Any]:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_cameras = int(db.scalar(select(func.count(Camera.id))) or 0)
    online = int(
        db.scalar(select(func.count(Camera.id)).where(Camera.status == "ONLINE", Camera.enabled.is_(True))) or 0
    )
    offline = int(
        db.scalar(select(func.count(Camera.id)).where(Camera.status == "OFFLINE", Camera.enabled.is_(True))) or 0
    )
    degraded = int(
        db.scalar(select(func.count(Camera.id)).where(Camera.status == "DEGRADED", Camera.enabled.is_(True))) or 0
    )
    disabled = int(db.scalar(select(func.count(Camera.id)).where(Camera.enabled.is_(False))) or 0)
    total_events = int(db.scalar(select(func.count(AnalyticsEvent.id))) or 0)
    events_today = int(db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.occurred_at >= today)) or 0)
    open_alerts = int(db.scalar(select(func.count(Alert.id)).where(Alert.status == "OPEN")) or 0)
    critical_alerts = int(
        db.scalar(select(func.count(Alert.id)).where(Alert.status == "OPEN", Alert.severity == "CRITICAL")) or 0
    )
    watchlist_entries = int(
        db.scalar(select(func.count(WatchlistEntry.id)).where(WatchlistEntry.active.is_(True))) or 0
    )
    active_sources = int(
        db.scalar(select(func.count(func.distinct(Camera.source_protocol))).where(Camera.enabled.is_(True))) or 0
    )
    last_event = db.scalar(select(AnalyticsEvent.occurred_at).order_by(AnalyticsEvent.occurred_at.desc()))
    last_alert = db.scalar(select(Alert.created_at).order_by(Alert.created_at.desc()))
    return {
        "total_cameras": total_cameras,
        "online_cameras": online,
        "offline_cameras": offline,
        "degraded_cameras": degraded,
        "disabled_cameras": disabled,
        "total_events": total_events,
        "events_today": events_today,
        "open_alerts": open_alerts,
        "critical_alerts": critical_alerts,
        "watchlist_entries": watchlist_entries,
        "active_sources": active_sources,
        "last_event_at": last_event,
        "last_alert_at": last_alert,
    }


def make_simulator_payload(
    camera: Camera,
    request_identifier: str | None = None,
    request_event_type: str = "ANPR",
    request_entity_type: Literal["VEHICLE", "PERSON", "OBJECT"] | None = None,
    request_confidence: float = 0.96,
    request_vehicle_type: str = "CAR",
    idempotency_key: str | None = None,
) -> AnalyticsEventCreate:
    identifier = normalize_identifier(request_identifier or "GJ01AB1234")
    return AnalyticsEventCreate(
        camera_id=camera.camera_id,
        event_type=request_event_type,
        occurred_at=utc_now(),
        entity_type=request_entity_type,
        entity_identifier=identifier,
        confidence=request_confidence,
        vehicle_type=request_vehicle_type,
        source=f"adapter:{camera.source_protocol.lower()}",
        metadata={
            "simulated": True,
            "adapter": camera.source_protocol,
            "stream_endpoint": camera.stream_endpoint,
            "zone": camera.zone,
        },
        idempotency_key=idempotency_key or f"sim-{camera.camera_id}-{uuid.uuid4().hex}",
    )
