import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Alert, AnalyticsEvent, Camera, CameraStatusHistory
from .analytics_service import (
    ingest_event,
    make_simulator_payload,
)
from .audit import record_audit


def run_heartbeat_cycle(db: Session) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    changes: list[dict[str, Any]] = []
    cameras = db.scalars(select(Camera).where(Camera.enabled.is_(True), Camera.stream_endpoint.like("sim://%"))).all()
    for camera in cameras:
        previous = camera.status
        configured_probe_status = str((camera.extra_data or {}).get("probe_status", previous)).upper()
        next_status = (
            configured_probe_status if configured_probe_status in {"ONLINE", "OFFLINE", "DEGRADED"} else previous
        )
        camera.last_heartbeat = now
        camera.status = next_status
        if previous != next_status:
            db.add(
                CameraStatusHistory(
                    camera_id=camera.id,
                    status=next_status,
                    heartbeat_at=now,
                    reason="simulated_probe",
                )
            )
            record_audit(
                db,
                action="camera.health.changed",
                resource_type="camera",
                resource_id=camera.id,
                details={"from": previous, "to": next_status, "source": "simulated_probe"},
            )
            changes.append(
                {
                    "camera_id": camera.camera_id,
                    "status": next_status,
                    "last_heartbeat": now,
                }
            )
    db.commit()
    return changes


def run_simulator_cycle(db: Session) -> tuple[AnalyticsEvent, Alert | None]:
    cameras = db.scalars(select(Camera).where(Camera.enabled.is_(True)).order_by(Camera.camera_id.asc())).all()
    if not cameras:
        raise RuntimeError("No enabled cameras are available")
    event_count = int(db.scalar(select(func.count(AnalyticsEvent.id))) or 0)
    camera = cameras[event_count % len(cameras)]
    identifier = "GJ01AB1234" if event_count % 3 != 2 else "GJ01CD9012"
    payload = make_simulator_payload(
        camera,
        request_identifier=identifier,
        request_event_type="ANPR",
        request_confidence=0.975,
        idempotency_key=f"background-{camera.camera_id}-{event_count}-{uuid.uuid4().hex[:8]}",
    )
    event, alert, _duplicate = ingest_event(db, payload)
    return event, alert
