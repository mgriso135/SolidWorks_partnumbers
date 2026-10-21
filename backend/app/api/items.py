from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Item, User, utcnow
from ..schemas import ItemOut, ItemPage
from ..services import audit

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=ItemPage)
def list_items(
    q: str | None = None,
    rule_key: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemPage:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conditions = [Item.tenant_id == user.tenant_id]
    if q:
        needle = f"%{q.strip()}%"
        conditions.append(or_(Item.code.ilike(needle), Item.external_ref.ilike(needle)))
    if rule_key:
        conditions.append(Item.rule_key == rule_key)
    if status_filter:
        conditions.append(Item.status == status_filter)

    total = db.scalar(select(func.count(Item.id)).where(*conditions)) or 0
    items = db.scalars(
        select(Item).where(*conditions).order_by(Item.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return ItemPage(
        items=[ItemOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/lookup", response_model=ItemOut)
def lookup_item(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemOut:
    item = db.scalar(
        select(Item).where(
            Item.tenant_id == user.tenant_id,
            func.upper(Item.code) == code.strip().upper(),
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    return ItemOut.model_validate(item)


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ItemOut:
    item = db.scalar(select(Item).where(Item.id == item_id, Item.tenant_id == user.tenant_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return ItemOut.model_validate(item)


@router.post("/{item_id}/void", response_model=ItemOut)
def void_item(
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
) -> ItemOut:
    item = db.scalar(select(Item).where(Item.id == item_id, Item.tenant_id == user.tenant_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if item.status == "void":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item is already void")
    item.status = "void"
    item.voided_at = utcnow()
    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="item.voided",
        entity_type="item",
        entity_id=item.id,
        details={"code": item.code},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(item)
    return ItemOut.model_validate(item)
