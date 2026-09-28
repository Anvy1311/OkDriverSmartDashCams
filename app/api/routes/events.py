from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_user, get_event_actor, require_roles
from ...models import Alert, AnalyticsEvent, Camera, User
from ...realtime import realtime
from ...schemas import (
    AnalyticsEventCreate,
    AnalyticsEventOut,
    EntityHistoryResponse,
    EventIngestResponse,
    EventListResponse,
    SimulatorRequest,
)
from ...services.analytics_service import (
    alert_to_dict,
    event_to_dict,
    ingest_event,
    list_history,
    make_simulator_payload,
)

router = APIRouter(prefix="/api/v1/events", tags=["Analytics events"])


def _event_response(db: Session, event: AnalyticsEvent) -> AnalyticsEventOut:
    alert = db.scalar(select(Alert).where(Alert.event_id == event.id))
    return AnalyticsEventOut.model_validate(event_to_dict(event, alert))


@router.post("", response_model=EventIngestResponse, status_code=202)
async def receive_event(
    payload: AnalyticsEventCreate,
    db: Session = Depends(get_db),
    actor: User | None = Depends(get_event_actor),
) -> EventIngestResponse:
    try:
        event, alert, duplicate = ingest_event(db, payload, actor.id if actor else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    event_data = event_to_dict(event, alert)
    if not duplicate:
        await realtime.broadcast(
            {"type": "detection", "event": event_data, "alert": alert_to_dict(alert) if alert else None}
        )
    return EventIngestResponse(
        event=AnalyticsEventOut.model_validate(event_data),
        alert=alert_to_dict(alert) if alert else None,
        duplicate=duplicate,
    )


@router.get("", response_model=EventListResponse)
def list_events(
    camera_id: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, max_length=160),
    entity_identifier: str | None = Query(default=None, max_length=160),
    event_type: str | None = Query(default=None, max_length=64),
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventListResponse:
    filters = []
    if camera_id:
        filters.append(AnalyticsEvent.camera_id == camera_id)
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                AnalyticsEvent.entity_identifier.ilike(term),
                AnalyticsEvent.camera_id.ilike(term),
                AnalyticsEvent.event_type.ilike(term),
            )
        )
    if entity_identifier:
        filters.append(
            func.upper(func.replace(AnalyticsEvent.entity_identifier, " ", ""))
            == "".join(entity_identifier.split()).upper()
        )
    if event_type:
        filters.append(AnalyticsEvent.event_type == event_type.upper())
    if from_time:
        filters.append(AnalyticsEvent.occurred_at >= from_time)
    if to_time:
        filters.append(AnalyticsEvent.occurred_at <= to_time)
    total = int(db.scalar(select(func.count(AnalyticsEvent.id)).where(*filters)) or 0)
    events = db.scalars(
        select(AnalyticsEvent)
        .where(*filters)
        .order_by(AnalyticsEvent.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return EventListResponse(
        items=[_event_response(db, event) for event in events],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/history", response_model=EntityHistoryResponse)
def search_history(
    identifier: str = Query(min_length=2, max_length=160),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityHistoryResponse:
    return EntityHistoryResponse.model_validate(list_history(db, identifier))


@router.get("/entities/{identifier}/history", response_model=EntityHistoryResponse)
def entity_history(
    identifier: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EntityHistoryResponse:
    return EntityHistoryResponse.model_validate(list_history(db, identifier))


@router.post("/simulator/emit", response_model=EventIngestResponse, status_code=202)
async def simulator_emit(
    payload: SimulatorRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("operator", "admin")),
) -> EventIngestResponse:
    camera = None
    if payload.camera_id:
        camera = db.scalar(select(Camera).where(Camera.camera_id == payload.camera_id, Camera.enabled.is_(True)))
    if not camera:
        camera = db.scalar(select(Camera).where(Camera.enabled.is_(True)).order_by(Camera.camera_id.asc()))
    if not camera:
        raise HTTPException(status_code=404, detail="No enabled camera is available")
    event_payload = make_simulator_payload(
        camera,
        request_identifier=payload.entity_identifier,
        request_event_type=payload.event_type,
        request_entity_type=payload.entity_type,
        request_confidence=payload.confidence,
        request_vehicle_type=payload.vehicle_type,
        idempotency_key=payload.idempotency_key,
    )
    event, alert, duplicate = ingest_event(db, event_payload, actor.id)
    event_data = event_to_dict(event, alert)
    if not duplicate:
        await realtime.broadcast(
            {"type": "detection", "event": event_data, "alert": alert_to_dict(alert) if alert else None}
        )
    return EventIngestResponse(
        event=AnalyticsEventOut.model_validate(event_data),
        alert=alert_to_dict(alert) if alert else None,
        duplicate=duplicate,
    )


@router.post("/simulator/tick", response_model=EventIngestResponse, status_code=202)
async def simulator_tick(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin", "operator")),
) -> EventIngestResponse:
    cameras = db.scalars(select(Camera).where(Camera.enabled.is_(True)).order_by(Camera.camera_id.asc())).all()
    if not cameras:
        raise HTTPException(status_code=404, detail="No enabled camera is available")
    sequence = int(db.scalar(select(func.count(AnalyticsEvent.id))) or 0)
    camera = cameras[sequence % len(cameras)]
    identifier = "GJ01AB1234" if sequence % 3 != 2 else "GJ01CD9012"
    event_payload = make_simulator_payload(
        camera,
        request_identifier=identifier,
        request_event_type="ANPR",
        request_confidence=0.97,
        idempotency_key=f"tick-{camera.camera_id}-{sequence}",
    )
    event, alert, duplicate = ingest_event(db, event_payload, actor.id)
    event_data = event_to_dict(event, alert)
    if not duplicate:
        await realtime.broadcast(
            {"type": "detection", "event": event_data, "alert": alert_to_dict(alert) if alert else None}
        )
    return EventIngestResponse(
        event=AnalyticsEventOut.model_validate(event_data),
        alert=alert_to_dict(alert) if alert else None,
        duplicate=duplicate,
    )
