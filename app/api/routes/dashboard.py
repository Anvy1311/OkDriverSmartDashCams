from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_user
from ...models import Alert, AnalyticsEvent, AuditLog, Camera, User
from ...schemas import DashboardStats
from ...services.analytics_service import alert_to_dict, get_dashboard_stats

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    return DashboardStats.model_validate(get_dashboard_stats(db))


@router.get("/activity")
def activity(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    entries = db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)).all()
    users = {user.id: user.username for user in db.scalars(select(User)).all()}
    return [
        {
            "id": entry.id,
            "actor": users.get(entry.actor_id or 0, "system" if entry.actor_id is None else "user"),
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "details": entry.details,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]


@router.get("/recent")
def recent(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    events = db.scalars(select(AnalyticsEvent).order_by(desc(AnalyticsEvent.occurred_at)).limit(limit)).all()
    alerts = db.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(limit)).all()
    cameras = db.scalars(
        select(Camera).where(Camera.enabled.is_(True)).order_by(Camera.updated_at.desc()).limit(limit)
    ).all()
    return {
        "events": [
            {
                "id": event.id,
                "camera_id": event.camera_id,
                "event_type": event.event_type,
                "entity_identifier": event.entity_identifier,
                "confidence": event.confidence,
                "occurred_at": event.occurred_at,
            }
            for event in events
        ],
        "alerts": [alert_to_dict(alert) for alert in alerts],
        "cameras": [
            {
                "camera_id": camera.camera_id,
                "name": camera.name,
                "status": camera.status,
                "last_heartbeat": camera.last_heartbeat,
            }
            for camera in cameras
        ],
        "generated_at": datetime.now(timezone.utc),
    }
