from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Item
from ...schemas import ErpReconcileOut, ErpReconcileRequest, ErpReconcileResult
from .. import audit
from .base import ErpAdapter, ErpAdapterError


def reconcile_items(
    db: Session,
    *,
    tenant_id: str,
    adapter: ErpAdapter,
    request: ErpReconcileRequest,
    actor_id: str | None,
    actor_type: str,
    ip: str | None = None,
) -> ErpReconcileOut:
    """Compare non-void PartCode items with the ERP.

    A reserved item found in ERP is marked committed unless this is a dry run.
    A committed item is reported as matched. Missing items are not downgraded:
    ERP is authoritative, so PartCode reports the mismatch but does not change
    the item status.
    """
    conditions = [Item.tenant_id == tenant_id, Item.status != "void"]
    if request.codes:
        conditions.append(Item.code.in_(request.codes))
    items = db.scalars(
        select(Item).where(*conditions).order_by(Item.created_at.desc()).limit(request.limit)
    ).all()

    results: list[ErpReconcileResult] = []
    found = 0
    not_found = 0
    committed = 0
    would_commit = 0
    errors = 0

    for item in items:
        try:
            erp_item = adapter.lookup(item.code)
        except ErpAdapterError as exc:
            errors += 1
            results.append(
                ErpReconcileResult(
                    item_id=item.id,
                    code=item.code,
                    partcode_status=item.status,
                    erp_found=False,
                    action="error",
                    error=str(exc),
                )
            )
            continue

        if erp_item is None:
            not_found += 1
            results.append(
                ErpReconcileResult(
                    item_id=item.id,
                    code=item.code,
                    partcode_status=item.status,
                    erp_found=False,
                    action="missing",
                )
            )
            continue

        found += 1
        action = "matched"
        if item.status == "reserved":
            if request.dry_run:
                would_commit += 1
                action = "would_commit"
            else:
                previous_status = item.status
                item.status = "committed"
                committed += 1
                action = "committed"
                audit.record(
                    db,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    actor_type=actor_type,
                    action="item.committed",
                    entity_type="item",
                    entity_id=item.id,
                    details={
                        "code": item.code,
                        "from": previous_status,
                        "to": item.status,
                        "adapter": adapter.name,
                        "external_id": erp_item.external_id,
                        "erp_status": erp_item.status,
                    },
                    ip=ip,
                )

        results.append(
            ErpReconcileResult(
                item_id=item.id,
                code=item.code,
                partcode_status=item.status,
                erp_found=True,
                erp_status=erp_item.status,
                external_id=erp_item.external_id,
                action=action,
            )
        )

    if not request.dry_run:
        db.commit()

    return ErpReconcileOut(
        adapter=adapter.name,
        checked=len(results),
        found=found,
        not_found=not_found,
        committed=committed,
        would_commit=would_commit,
        errors=errors,
        dry_run=request.dry_run,
        results=results,
    )
