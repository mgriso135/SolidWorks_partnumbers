from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def record(
    db: Session,
    *,
    tenant_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    actor_id: str | None = None,
    actor_type: str = "user",
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip=ip,
    )
    db.add(entry)
    db.flush()
    return entry
