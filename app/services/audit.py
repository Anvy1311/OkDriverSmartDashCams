from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def record_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str | int | None,
    actor_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=details or {},
    )
    db.add(entry)
    return entry


def audit_to_dict(entry: AuditLog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "actor_id": entry.actor_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "details": entry.details,
        "created_at": entry.created_at,
    }
