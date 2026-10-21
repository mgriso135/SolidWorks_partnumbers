from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import User
from ..schemas import RuleCreate, RuleOut, RuleUpdate
from ..services import audit
from ..services import rules as rule_service

router = APIRouter(prefix="/rules", tags=["rules"])

_EDITOR = require_roles("admin", "editor")


@router.get("", response_model=list[RuleOut])
def list_rules(
    status_filter: str | None = None,
    document_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor", "viewer")),
) -> list[RuleOut]:
    items = rule_service.list_latest_rules(
        db,
        user.tenant_id,
        status_filter=status_filter,
        document_type=document_type,
    )
    return [RuleOut.model_validate(rule) for rule in items]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_EDITOR),
) -> RuleOut:
    try:
        rule = rule_service.create_rule(db, user.tenant_id, user, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rule with this key already exists",
        ) from None
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="rule.created",
        entity_type="rule",
        entity_id=rule.id,
        details={"key": rule.key, "version": rule.version, "name": rule.name},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return RuleOut.model_validate(rule)


@router.get("/{rule_id}", response_model=RuleOut)
def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor", "viewer")),
) -> RuleOut:
    rule = rule_service.get_rule(db, user.tenant_id, rule_id)
    return RuleOut.model_validate(rule)


@router.get("/{rule_id}/versions", response_model=list[RuleOut])
def get_rule_versions(
    rule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor", "viewer")),
) -> list[RuleOut]:
    rule = rule_service.get_rule(db, user.tenant_id, rule_id)
    versions = rule_service.list_versions(db, user.tenant_id, rule.key)
    return [RuleOut.model_validate(item) for item in versions]


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_EDITOR),
) -> RuleOut:
    rule = rule_service.get_rule(db, user.tenant_id, rule_id)
    updated = rule_service.update_rule(db, user.tenant_id, rule, payload, user)
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="rule.updated",
        entity_type="rule",
        entity_id=updated.id,
        details={
            "key": updated.key,
            "version": updated.version,
            "previous_version": rule.version,
            "status": updated.status,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return RuleOut.model_validate(updated)


@router.post("/{rule_id}/archive", response_model=RuleOut)
def archive_rule(
    rule_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_EDITOR),
) -> RuleOut:
    rule = rule_service.get_rule(db, user.tenant_id, rule_id)
    archived = rule_service.archive_rule(db, rule)
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="rule.archived",
        entity_type="rule",
        entity_id=archived.id,
        details={"key": archived.key, "version": archived.version},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return RuleOut.model_validate(archived)
