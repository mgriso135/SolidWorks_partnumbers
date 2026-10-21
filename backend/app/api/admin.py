from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import ApiKey, AuditLog, Item, Rule, User, utcnow
from ..schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    AuditOut,
    AuditPage,
    DashboardStats,
    ItemOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from ..security import generate_api_key, hash_password
from ..services import audit

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN = require_roles("admin")
_AUDIT = require_roles("admin", "editor")
_ANY = require_roles("admin", "editor", "viewer")


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(_ADMIN)) -> list[UserOut]:
    users = db.scalars(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at)
    ).all()
    return [UserOut.model_validate(item) for item in users]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_ADMIN),
) -> UserOut:
    email = payload.email.strip().lower()
    existing = db.scalar(select(User).where(User.tenant_id == user.tenant_id, User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    created = User(
        tenant_id=user.tenant_id,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        active=True,
    )
    db.add(created)
    db.flush()
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="user.created",
        entity_type="user",
        entity_id=created.id,
        details={"email": email, "role": created.role},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(created)
    return UserOut.model_validate(created)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_ADMIN),
) -> UserOut:
    target = db.scalar(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.id == user.id and (
        payload.active is False or (payload.role is not None and payload.role != "admin")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate or demote your own admin account",
        )
    if payload.role is not None:
        target.role = payload.role
    if payload.active is not None:
        target.active = payload.active
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="user.updated",
        entity_type="user",
        entity_id=target.id,
        details={"role": target.role, "active": target.active},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(target)
    return UserOut.model_validate(target)


@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(db: Session = Depends(get_db), user: User = Depends(_ADMIN)) -> list[ApiKeyOut]:
    keys = db.scalars(
        select(ApiKey).where(ApiKey.tenant_id == user.tenant_id).order_by(ApiKey.created_at.desc())
    ).all()
    return [ApiKeyOut.model_validate(key) for key in keys]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_ADMIN),
) -> ApiKeyCreated:
    secret, prefix, key_hash = generate_api_key()
    api_key = ApiKey(
        tenant_id=user.tenant_id,
        name=payload.name,
        prefix=prefix,
        key_hash=key_hash,
    )
    db.add(api_key)
    db.flush()
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="api_key.created",
        entity_type="api_key",
        entity_id=api_key.id,
        details={"name": api_key.name, "prefix": api_key.prefix},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(api_key)
    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
        key=secret,
    )


@router.delete("/api-keys/{key_id}", response_model=ApiKeyOut)
def revoke_api_key(
    key_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_ADMIN),
) -> ApiKeyOut:
    api_key = db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == user.tenant_id)
    )
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    if api_key.revoked_at is None:
        api_key.revoked_at = utcnow()
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="api_key.revoked",
        entity_type="api_key",
        entity_id=api_key.id,
        details={"prefix": api_key.prefix},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(api_key)
    return ApiKeyOut.model_validate(api_key)


@router.get("/audit", response_model=AuditPage)
def list_audit(
    action: str | None = None,
    actor_id: str | None = None,
    entity_type: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(_AUDIT),
) -> AuditPage:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conditions = [AuditLog.tenant_id == user.tenant_id]
    if action:
        conditions.append(AuditLog.action == action)
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if since:
        conditions.append(AuditLog.created_at >= since)
    if until:
        conditions.append(AuditLog.created_at <= until)

    total = db.scalar(select(func.count(AuditLog.id)).where(*conditions)) or 0
    entries = db.scalars(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return AuditPage(
        items=[AuditOut.model_validate(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=DashboardStats)
def stats(db: Session = Depends(get_db), user: User = Depends(_ANY)) -> DashboardStats:
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_ago = now - timedelta(days=30)

    active_rules = (
        db.scalar(
            select(func.count(distinct(Rule.key))).where(
                Rule.tenant_id == user.tenant_id, Rule.status == "active"
            )
        )
        or 0
    )
    items_total = (
        db.scalar(select(func.count(Item.id)).where(Item.tenant_id == user.tenant_id)) or 0
    )
    items_30d = (
        db.scalar(
            select(func.count(Item.id)).where(
                Item.tenant_id == user.tenant_id, Item.created_at >= month_ago
            )
        )
        or 0
    )
    items_today = (
        db.scalar(
            select(func.count(Item.id)).where(
                Item.tenant_id == user.tenant_id, Item.created_at >= today
            )
        )
        or 0
    )
    active_users = (
        db.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == user.tenant_id, User.active.is_(True)
            )
        )
        or 0
    )
    source_rows = db.execute(
        select(Item.source, func.count(Item.id))
        .where(Item.tenant_id == user.tenant_id)
        .group_by(Item.source)
    ).all()
    by_source = {source: count for source, count in source_rows}

    recent_items = db.scalars(
        select(Item)
        .where(Item.tenant_id == user.tenant_id)
        .order_by(Item.created_at.desc())
        .limit(5)
    ).all()
    recent_audit = db.scalars(
        select(AuditLog)
        .where(AuditLog.tenant_id == user.tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
    ).all()

    return DashboardStats(
        active_rules=active_rules,
        items_total=items_total,
        items_30d=items_30d,
        items_today=items_today,
        active_users=active_users,
        by_source=by_source,
        recent_items=[ItemOut.model_validate(item) for item in recent_items],
        recent_audit=[AuditOut.model_validate(entry) for entry in recent_audit],
    )
