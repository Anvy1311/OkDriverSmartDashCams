from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import get_current_user, require_roles
from ...models import User, WatchlistEntry
from ...schemas import WatchlistCreate, WatchlistOut, WatchlistUpdate
from ...services.audit import record_audit

router = APIRouter(prefix="/api/v1/watchlist", tags=["Watchlist"], dependencies=[Depends(get_current_user)])


def _entry_response(entry: WatchlistEntry) -> WatchlistOut:
    return WatchlistOut.model_validate(entry)


@router.get("", response_model=list[WatchlistOut])
def list_watchlist(
    q: str | None = Query(default=None, max_length=120),
    entity_type: str | None = Query(default=None, max_length=32),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[WatchlistOut]:
    filters = []
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                WatchlistEntry.identifier.ilike(term),
                WatchlistEntry.display_name.ilike(term),
                WatchlistEntry.reason.ilike(term),
            )
        )
    if entity_type:
        filters.append(WatchlistEntry.entity_type == entity_type.upper())
    if active is not None:
        filters.append(WatchlistEntry.active.is_(active))
    entries = db.scalars(
        select(WatchlistEntry).where(*filters).order_by(WatchlistEntry.severity.desc(), WatchlistEntry.identifier.asc())
    ).all()
    return [_entry_response(entry) for entry in entries]


@router.post("", response_model=WatchlistOut, status_code=201)
def create_watchlist(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> WatchlistOut:
    identifier = "".join(payload.identifier.split()).upper()
    duplicate = db.scalar(
        select(WatchlistEntry).where(
            func.upper(func.replace(WatchlistEntry.identifier, " ", "")) == identifier,
            WatchlistEntry.entity_type == payload.entity_type,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Watchlist identifier already exists")
    data = payload.model_dump()
    data["identifier"] = identifier
    entry = WatchlistEntry(**data)
    db.add(entry)
    db.flush()
    record_audit(db, "watchlist.created", "watchlist", entry.id, actor.id, {"identifier": identifier})
    db.commit()
    db.refresh(entry)
    return _entry_response(entry)


@router.get("/{entry_id}", response_model=WatchlistOut)
def get_watchlist_entry(entry_id: int, db: Session = Depends(get_db)) -> WatchlistOut:
    entry = db.get(WatchlistEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    return _entry_response(entry)


@router.patch("/{entry_id}", response_model=WatchlistOut)
def update_watchlist(
    entry_id: int,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> WatchlistOut:
    entry = db.get(WatchlistEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("identifier"):
        values["identifier"] = "".join(values["identifier"].split()).upper()
    candidate_identifier = values.get("identifier", entry.identifier)
    candidate_type = values.get("entity_type", entry.entity_type)
    duplicate = db.scalar(
        select(WatchlistEntry).where(
            WatchlistEntry.id != entry_id,
            WatchlistEntry.entity_type == candidate_type,
            func.upper(func.replace(WatchlistEntry.identifier, " ", "")) == candidate_identifier,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Watchlist identifier already exists")
    for key, value in values.items():
        if value is not None:
            setattr(entry, key, value)
    record_audit(db, "watchlist.updated", "watchlist", entry.id, actor.id, {"fields": sorted(values.keys())})
    db.commit()
    db.refresh(entry)
    return _entry_response(entry)


@router.delete("/{entry_id}", response_model=WatchlistOut)
def deactivate_watchlist(
    entry_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
) -> WatchlistOut:
    entry = db.get(WatchlistEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    entry.active = False
    record_audit(db, "watchlist.deactivated", "watchlist", entry.id, actor.id)
    db.commit()
    db.refresh(entry)
    return _entry_response(entry)
