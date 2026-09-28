from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...dependencies import get_current_user
from ...models import User

router = APIRouter(prefix="/api/v1/system", tags=["System"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "database": "ok",
        "timestamp": datetime.now(timezone.utc),
    }


@router.get("/map-config")
def map_config(_user: User = Depends(get_current_user)) -> dict[str, str | int]:
    return {
        "tile_url": settings.map_tile_url,
        "attribution": settings.map_attribution,
        "max_zoom": settings.map_max_zoom,
        "referrer_policy": "strict-origin-when-cross-origin",
    }


@router.get("/readiness")
def readiness(db: Session = Depends(get_db)) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "checks": {"database": "ok", "realtime": "ok"}}
