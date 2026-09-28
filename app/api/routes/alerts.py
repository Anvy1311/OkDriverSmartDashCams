from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_user, require_roles
from ...models import Alert, Camera, User, WatchlistEntry
from ...realtime import realtime
from ...schemas import AlertListResponse, AlertOut
from ...services.analytics_service import alert_to_dict
from ...services.audit import record_audit

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"], dependencies=[Depends(get_current_user)])


def _get_alert(db: Session, alert_id: str) -> Alert:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _response(db: Session, alert: Alert) -> AlertOut:
    camera = db.scalar(select(Camera).where(Camera.camera_id == alert.camera_id))
    entry = db.get(WatchlistEntry, alert.watchlist_entry_id)
    return AlertOut.model_validate(alert_to_dict(alert, camera, entry))


@router.get("", response_model=AlertListResponse)
def list_alerts(
    alert_status: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None, max_length=24),
    camera_id: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> AlertListResponse:
    filters = []
    if alert_status:
        filters.append(Alert.status == alert_status.upper())
    if severity:
        filters.append(Alert.severity == severity.upper())
    if camera_id:
        filters.append(Alert.camera_id == camera_id)
    total = int(db.scalar(select(func.count(Alert.id)).where(*filters)) or 0)
    alerts = db.scalars(
        select(Alert).where(*filters).order_by(Alert.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AlertListResponse(
        items=[_response(db, alert) for alert in alerts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("operator", "admin")),
) -> AlertOut:
    alert = _get_alert(db, alert_id)
    if alert.status == "RESOLVED":
        raise HTTPException(status_code=409, detail="Resolved alerts cannot be acknowledged")
    from datetime import datetime, timezone

    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = actor.username
    record_audit(db, "alert.acknowledged", "alert", alert.id, actor.id)
    db.commit()
    db.refresh(alert)
    result = _response(db, alert)
    await realtime.broadcast({"type": "alert.updated", "alert": result.model_dump(mode="json")})
    return result


@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("operator", "admin")),
) -> AlertOut:
    alert = _get_alert(db, alert_id)
    from datetime import datetime, timezone

    alert.status = "RESOLVED"
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = actor.username
    if not alert.acknowledged_at:
        alert.acknowledged_at = alert.resolved_at
        alert.acknowledged_by = actor.username
    record_audit(db, "alert.resolved", "alert", alert.id, actor.id)
    db.commit()
    db.refresh(alert)
    result = _response(db, alert)
    await realtime.broadcast({"type": "alert.updated", "alert": result.model_dump(mode="json")})
    return result


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, db: Session = Depends(get_db)) -> AlertOut:
    return _response(db, _get_alert(db, alert_id))
