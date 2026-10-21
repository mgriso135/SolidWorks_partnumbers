from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import GenerateOut, GenerateRequest
from ..services import audit, generator
from ..services import rules as rule_service

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("/preview", response_model=GenerateOut)
def preview(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GenerateOut:
    rule = rule_service.get_active_rule(db, user.tenant_id, payload.rule_key)
    rendered = generator.preview_code(db, tenant_id=user.tenant_id, rule=rule, request=payload)
    return GenerateOut(
        code=rendered.code,
        rule_key=rule.key,
        rule_version=rule.version,
        status="preview",
        segments=rendered.segments,
    )


@router.post("", response_model=GenerateOut)
def generate(
    payload: GenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GenerateOut:
    rule = rule_service.get_active_rule(db, user.tenant_id, payload.rule_key)
    item, segments = generator.commit_code(
        db,
        tenant_id=user.tenant_id,
        rule=rule,
        request=payload,
        created_by=user.id,
    )
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="code.generated",
        entity_type="item",
        entity_id=item.id,
        details={
            "code": item.code,
            "rule_key": item.rule_key,
            "rule_version": item.rule_version,
            "source": item.source,
            "external_ref": item.external_ref,
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return GenerateOut(
        code=item.code,
        rule_key=item.rule_key,
        rule_version=item.rule_version,
        item_id=item.id,
        status=item.status,
        segments=segments,
        created_at=item.created_at,
    )
