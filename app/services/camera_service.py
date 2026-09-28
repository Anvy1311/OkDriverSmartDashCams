from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Camera, CameraStatusHistory
from .adapters import adapter_descriptor


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def camera_to_dict(camera: Camera) -> dict[str, Any]:
    return {
        "id": camera.id,
        "camera_id": camera.camera_id,
        "name": camera.name,
        "department": camera.department,
        "latitude": camera.latitude,
        "longitude": camera.longitude,
        "camera_type": camera.camera_type,
        "source_protocol": camera.source_protocol,
        "stream_endpoint": camera.stream_endpoint,
        "status": camera.status,
        "last_heartbeat": camera.last_heartbeat,
        "zone": camera.zone,
        "storage_provider": camera.storage_provider,
        "storage_bucket": camera.storage_bucket,
        "storage_retention_days": camera.storage_retention_days,
        "coverage_area": camera.coverage_area,
        "enabled": camera.enabled,
        "extra_data": camera.extra_data or {},
        "created_at": camera.created_at,
        "updated_at": camera.updated_at,
        "active_alert_count": 0,
        "highest_alert_severity": None,
        "stream_url": f"/api/v1/cameras/{camera.camera_id}/stream",
        "adapter": adapter_descriptor(camera),
    }


def camera_exists(db: Session, camera_id: str) -> Camera | None:
    return db.scalar(select(Camera).where(Camera.camera_id == camera_id))


def add_camera(db: Session, values: dict[str, Any]) -> Camera:
    camera = Camera(**values)
    db.add(camera)
    db.flush()
    return camera


def update_camera_values(camera: Camera, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if value is not None:
            setattr(camera, key, value)


def update_camera_heartbeat(
    db: Session,
    camera: Camera,
    status: str | None = None,
    reason: str | None = None,
) -> Camera:
    now = utc_now()
    previous_status = camera.status
    next_status = status or camera.status
    camera.last_heartbeat = now
    camera.status = next_status
    db.add(
        CameraStatusHistory(
            camera_id=camera.id,
            status=next_status,
            heartbeat_at=now,
            reason=reason,
        )
    )
    if previous_status != next_status:
        db.flush()
    return camera


def count_cameras(db: Session) -> int:
    return int(db.scalar(select(func.count(Camera.id))) or 0)


def get_camera_audit(db: Session, camera_id: int) -> list[dict[str, Any]]:
    from ..models import AuditLog

    entries = db.scalars(
        select(AuditLog)
        .where(AuditLog.resource_type == "camera", AuditLog.resource_id == str(camera_id))
        .order_by(AuditLog.created_at.desc())
    ).all()
    return [
        {
            "id": entry.id,
            "actor_id": entry.actor_id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "details": entry.details,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
