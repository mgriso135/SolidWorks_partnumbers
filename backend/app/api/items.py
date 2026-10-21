from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Item, User, utcnow
from ..schemas import ItemOut, ItemPage, ItemUpdate
from ..services import audit, generator
from ..services.errors import GenerationError

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


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: str,
    payload: ItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "editor")),
) -> ItemOut:
    item = db.scalar(select(Item).where(Item.id == item_id, Item.tenant_id == user.tenant_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if item.status == "void":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voided items cannot be edited",
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return ItemOut.model_validate(item)

    before = {
        "external_ref": item.external_ref,
        "notes": item.notes,
        "metadata_keys": sorted(item.payload),
    }

    if "external_ref" in changes:
        external_ref = generator.normalize_external_ref(changes["external_ref"])
        if external_ref != item.external_ref:
            generator.ensure_external_ref_available(
                db,
                tenant_id=user.tenant_id,
                external_ref=external_ref,
                exclude_item_id=item.id,
            )
        item.external_ref = external_ref

    if "notes" in changes:
        notes = changes["notes"]
        item.notes = notes.strip() if notes and notes.strip() else None

    if "metadata" in changes:
        item.payload = changes["metadata"] or {}

    audit.record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="item.updated",
        entity_type="item",
        entity_id=item.id,
        details={
            "code": item.code,
            "changed": sorted(changes),
            "before": before,
            "after": {
                "external_ref": item.external_ref,
                "notes": item.notes,
                "metadata_keys": sorted(item.payload),
            },
        },
        ip=request.client.host if request.client else None,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "external_ref" in changes:
            generator.ensure_external_ref_available(
                db,
                tenant_id=user.tenant_id,
                external_ref=changes["external_ref"],
                exclude_item_id=item.id,
            )
        raise GenerationError(
            "CONFLICT",
            "Could not update the item because another value is already in use",
            status_code=409,
        ) from exc
    db.refresh(item)
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
