import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any
from urllib.parse import parse_qsl, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_user, require_roles
from ...models import Camera, CameraStatusHistory, User
from ...realtime import realtime
from ...schemas import (
    BulkCameraRequest,
    CameraCreate,
    CameraListResponse,
    CameraOut,
    CameraUpdate,
    GapAnalysisResponse,
)
from ...services.adapters import adapter_descriptor, get_adapter
from ...services.analytics_service import camera_alert_state, ensure_utc
from ...services.audit import record_audit
from ...services.camera_service import (
    add_camera,
    camera_to_dict,
    get_camera_audit,
    update_camera_heartbeat,
    update_camera_values,
)

router = APIRouter(prefix="/api/v1/cameras", tags=["Camera registry"], dependencies=[Depends(get_current_user)])


def _camera_response(db: Session, camera: Camera) -> CameraOut:
    response = camera_to_dict(camera)
    active_alert_count, highest_alert_severity = camera_alert_state(db, camera.camera_id)
    response["active_alert_count"] = active_alert_count
    response["highest_alert_severity"] = highest_alert_severity
    return CameraOut.model_validate(response)


def _validate_stream_reference(value: str) -> str:
    parsed = urlparse(value.strip())
    allowed_schemes = {"http", "https", "rtsp", "rtsps", "hls", "sim", "vault", "onvif"}
    sensitive_query_names = {
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "apikey",
        "api_key",
        "key",
        "secret",
        "signature",
        "sig",
        "auth",
    }
    if parsed.scheme.lower() not in allowed_schemes or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Use an approved secret-free stream reference")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Store a secret-free stream reference, not URL credentials")
    if any(name.lower() in sensitive_query_names for name, _value in parse_qsl(parsed.query, keep_blank_values=True)):
        raise HTTPException(
            status_code=422, detail="Stream references must not contain credential or signature parameters"
        )
    return value.strip()


@router.get("", response_model=CameraListResponse)
def list_cameras(
    q: str | None = Query(default=None, max_length=120),
    camera_status: str | None = Query(default=None, alias="status"),
    department: str | None = Query(default=None, max_length=180),
    protocol: str | None = Query(default=None, max_length=40),
    zone: str | None = Query(default=None, max_length=120),
    enabled: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> CameraListResponse:
    filters = []
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                Camera.camera_id.ilike(term),
                Camera.name.ilike(term),
                Camera.zone.ilike(term),
                Camera.department.ilike(term),
            )
        )
    if camera_status:
        filters.append(Camera.status == camera_status.upper())
    if department:
        filters.append(Camera.department == department)
    if protocol:
        filters.append(Camera.source_protocol == protocol.upper())
    if zone:
        filters.append(Camera.zone == zone)
    if enabled is not None:
        filters.append(Camera.enabled.is_(enabled))
    total = int(db.scalar(select(func.count(Camera.id)).where(*filters)) or 0)
    cameras = db.scalars(
        select(Camera).where(*filters).order_by(Camera.name.asc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return CameraListResponse(
        items=[_camera_response(db, camera) for camera in cameras],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export.csv")
def export_cameras(
    department: str | None = Query(default=None, max_length=180),
    db: Session = Depends(get_db),
) -> Response:
    query = select(Camera).order_by(Camera.camera_id.asc())
    if department:
        query = query.where(Camera.department == department)
    cameras = db.scalars(query).all()
    output = StringIO()
    fields = [
        "camera_id",
        "name",
        "department",
        "latitude",
        "longitude",
        "camera_type",
        "source_protocol",
        "stream_endpoint",
        "status",
        "zone",
        "storage_provider",
        "storage_bucket",
        "storage_retention_days",
        "enabled",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for camera in cameras:
        writer.writerow({field: getattr(camera, field) for field in fields})
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=okdriver-cameras.csv"},
    )


@router.get("/gap-analysis", response_model=GapAnalysisResponse)
def gap_analysis(db: Session = Depends(get_db)) -> GapAnalysisResponse:
    expected_zones = {
        "West Ahmedabad",
        "RTO East",
        "Sabarmati Corridor",
        "Gandhinagar North",
        "South Ahmedabad",
        "East Ahmedabad",
        "North Gujarat",
        "South Gujarat",
    }
    rows = db.execute(select(Camera.zone, Camera.status, Camera.created_at)).all()
    present_zones = {row[0] for row in rows if row[0]}
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row[1]] = status_counts.get(row[1], 0) + 1
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    aging = len([row for row in rows if row[2] and ensure_utc(row[2]) < cutoff])
    return GapAnalysisResponse(
        total_zones=len(expected_zones),
        covered_zones=len(present_zones & expected_zones),
        uncovered_zones=sorted(expected_zones - present_zones),
        cameras_by_status=status_counts,
        aging_camera_count=aging,
        generated_at=datetime.now(timezone.utc),
    )


@router.post("/bulk", status_code=201)
def bulk_onboard(
    payload: BulkCameraRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> dict[str, Any]:
    created: list[str] = []
    skipped: list[str] = []
    for item in payload.cameras:
        item_data = item.model_dump()
        item_data["stream_endpoint"] = _validate_stream_reference(item_data["stream_endpoint"])
        if not item_data["enabled"]:
            item_data["status"] = "OFFLINE"
        if item_data.get("camera_id") in created or item_data["camera_id"] in skipped:
            skipped.append(item_data["camera_id"])
            continue
        if any(
            camera.camera_id == item_data["camera_id"]
            for camera in db.scalars(select(Camera).where(Camera.camera_id == item_data["camera_id"]))
        ):
            skipped.append(item_data["camera_id"])
            continue
        camera = add_camera(db, item_data)
        db.add(
            CameraStatusHistory(
                camera_id=camera.id,
                status=camera.status,
                heartbeat_at=camera.last_heartbeat or datetime.now(timezone.utc),
            )
        )
        created.append(camera.camera_id)
        record_audit(db, "camera.bulk_onboarded", "camera", camera.id, actor.id, {"source": "bulk_api"})
    db.commit()
    return {"created": created, "skipped": skipped, "created_count": len(created), "skipped_count": len(skipped)}


@router.post("/onboard", response_model=CameraOut, status_code=201)
def api_onboard(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> CameraOut:
    return _create_camera(payload, db, actor)


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> CameraOut:
    return _create_camera(payload, db, actor)


def _create_camera(payload: CameraCreate, db: Session, actor: User) -> CameraOut:
    data = payload.model_dump()
    data["stream_endpoint"] = _validate_stream_reference(data["stream_endpoint"])
    if not data["enabled"]:
        data["status"] = "OFFLINE"
    if db.scalar(select(Camera).where(Camera.camera_id == data["camera_id"])):
        raise HTTPException(status_code=409, detail="Camera ID already exists")
    camera = add_camera(db, data)
    db.add(
        CameraStatusHistory(
            camera_id=camera.id,
            status=camera.status,
            heartbeat_at=camera.last_heartbeat or datetime.now(timezone.utc),
        )
    )
    record_audit(db, "camera.created", "camera", camera.id, actor.id, {"source": "manual_or_api"})
    db.commit()
    db.refresh(camera)
    return _camera_response(db, camera)


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db)) -> CameraOut:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _camera_response(db, camera)


@router.patch("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: str,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> CameraOut:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("stream_endpoint"):
        values["stream_endpoint"] = _validate_stream_reference(values["stream_endpoint"])
    if values.get("enabled") is False:
        values["status"] = "OFFLINE"
    previous_status = camera.status
    update_camera_values(camera, values)
    if values.get("status") and values["status"] != previous_status:
        db.add(
            CameraStatusHistory(
                camera_id=camera.id,
                status=values["status"],
                heartbeat_at=datetime.now(timezone.utc),
                reason="manual_update",
            )
        )
    record_audit(db, "camera.updated", "camera", camera.id, actor.id, {"fields": sorted(values.keys())})
    db.commit()
    db.refresh(camera)
    result = _camera_response(db, camera)
    event_type = "camera.health" if previous_status != camera.status else "camera.updated"
    await realtime.broadcast({"type": event_type, "camera": result.model_dump(mode="json")})
    return result


@router.delete("/{camera_id}", response_model=CameraOut)
async def disable_camera(
    camera_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> CameraOut:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    camera.enabled = False
    camera.status = "OFFLINE"
    db.add(
        CameraStatusHistory(
            camera_id=camera.id,
            status=camera.status,
            heartbeat_at=datetime.now(timezone.utc),
            reason="disabled_by_operator",
        )
    )
    record_audit(db, "camera.disabled", "camera", camera.id, actor.id)
    db.commit()
    db.refresh(camera)
    result = _camera_response(db, camera)
    await realtime.broadcast({"type": "camera.health", "camera": result.model_dump(mode="json")})
    return result


@router.post("/{camera_id}/heartbeat", response_model=CameraOut)
async def camera_heartbeat(
    camera_id: str,
    status_value: str | None = Query(default=None, alias="status"),
    reason: str | None = Query(default=None, max_length=240),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("operator", "admin")),
) -> CameraOut:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not camera.enabled:
        raise HTTPException(status_code=409, detail="Disabled cameras cannot send heartbeats")
    next_status = (status_value or camera.status).upper()
    if next_status not in {"ONLINE", "OFFLINE", "DEGRADED"}:
        raise HTTPException(status_code=422, detail="Invalid camera status")
    update_camera_heartbeat(db, camera, next_status, reason)
    record_audit(db, "camera.heartbeat", "camera", camera.id, actor.id, {"status": next_status, "reason": reason})
    db.commit()
    db.refresh(camera)
    result = _camera_response(db, camera)
    await realtime.broadcast({"type": "camera.health", "camera": result.model_dump(mode="json")})
    return result


@router.get("/{camera_id}/audit")
def camera_audit(camera_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return get_camera_audit(db, camera.id)


@router.get("/{camera_id}/status-history")
def camera_status_history(camera_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    rows = db.scalars(
        select(CameraStatusHistory)
        .where(CameraStatusHistory.camera_id == camera.id)
        .order_by(CameraStatusHistory.heartbeat_at.desc())
    ).all()
    return [{"status": row.status, "heartbeat_at": row.heartbeat_at, "reason": row.reason} for row in rows]


@router.get("/{camera_id}/stream")
def camera_stream(
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles("operator", "admin")),
) -> Response:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not camera.enabled:
        raise HTTPException(status_code=409, detail="Disabled cameras do not have an active stream")
    svg = get_adapter(camera).render()
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store, max-age=0"})


@router.get("/{camera_id}/adapter-info")
def camera_adapter(camera_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    camera = db.scalar(select(Camera).where(Camera.camera_id == camera_id))
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return adapter_descriptor(camera)
