from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_api_key
from ..models import ApiKey, Item
from ..schemas import (
    ErpLookupOut,
    ErpReconcileOut,
    ErpReconcileRequest,
    GenerateOut,
    GenerateRequest,
    ItemOut,
    LookupOut,
    RuleOut,
)
from ..services import audit, generator
from ..services import rules as rule_service
from ..services.erp import (
    ErpAdapter,
    ErpAdapterError,
    ErpConfigurationError,
    build_erp_adapter,
    reconcile_items,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/pdm/rules", response_model=list[RuleOut])
def pdm_rules(
    document_type: str | None = None,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> list[RuleOut]:
    rules = rule_service.list_latest_rules(
        db,
        api_key.tenant_id,
        status_filter="active",
        document_type=document_type,
    )
    return [RuleOut.model_validate(rule) for rule in rules]


@router.post("/pdm/preview", response_model=GenerateOut)
def pdm_preview(
    payload: GenerateRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> GenerateOut:
    rule = rule_service.get_active_rule(db, api_key.tenant_id, payload.rule_key)
    rendered = generator.preview_code(db, tenant_id=api_key.tenant_id, rule=rule, request=payload)
    return GenerateOut(
        code=rendered.code,
        rule_key=rule.key,
        rule_version=rule.version,
        status="preview",
        segments=rendered.segments,
    )


@router.post("/pdm/reserve", response_model=GenerateOut)
def pdm_reserve(
    payload: GenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> GenerateOut:
    rule = rule_service.get_active_rule(db, api_key.tenant_id, payload.rule_key)
    payload.source = "pdm"
    item, segments = generator.commit_code(
        db,
        tenant_id=api_key.tenant_id,
        rule=rule,
        request=payload,
        created_by=None,
    )
    audit.record(
        db,
        tenant_id=api_key.tenant_id,
        actor_id=api_key.id,
        actor_type="api_key",
        action="code.generated",
        entity_type="item",
        entity_id=item.id,
        details={
            "code": item.code,
            "rule_key": item.rule_key,
            "rule_version": item.rule_version,
            "source": "pdm",
            "external_ref": item.external_ref,
            "api_key": api_key.prefix,
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


@router.get("/pdm/lookup", response_model=LookupOut)
def pdm_lookup(
    code: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> LookupOut:
    item = db.scalar(
        select(Item).where(
            Item.tenant_id == api_key.tenant_id,
            func.upper(Item.code) == code.strip().upper(),
        )
    )
    if item is None:
        return LookupOut(exists=False)
    return LookupOut(exists=True, item=ItemOut.model_validate(item))


@router.get("/pdm/validate", response_model=LookupOut)
def pdm_validate(
    code: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> LookupOut:
    return pdm_lookup(code=code, db=db, api_key=api_key)


def get_erp_adapter() -> ErpAdapter:
    """Indirection kept here so tests can replace the configured adapter."""
    return build_erp_adapter()


def _erp_configuration_error(exc: ErpConfigurationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "ERP_NOT_CONFIGURED",
            "message": str(exc),
            "fields": {},
        },
    )


@router.get("/erp/lookup", response_model=ErpLookupOut)
def erp_lookup(
    code: str,
    api_key: ApiKey = Depends(get_api_key),
) -> ErpLookupOut:
    """Look up a code in the configured ERP adapter."""
    code = code.strip()
    if not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_INPUT",
                "message": "code is required",
                "fields": {"code": "This field is required"},
            },
        )
    try:
        adapter = get_erp_adapter()
        item = adapter.lookup(code)
    except ErpConfigurationError as exc:
        raise _erp_configuration_error(exc) from exc
    except ErpAdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "ERP_UNAVAILABLE",
                "message": str(exc),
                "fields": {},
            },
        ) from exc

    if item is None:
        return ErpLookupOut(
            found=False,
            code=code,
            adapter=adapter.name,
            message=(
                "Stub ERP adapter has no data" if adapter.name == "stub" else "Not found in ERP"
            ),
        )
    return ErpLookupOut(
        found=True,
        code=item.code,
        adapter=adapter.name,
        external_id=item.external_id,
        status=item.status,
        description=item.description,
    )


@router.post("/erp/reconcile", response_model=ErpReconcileOut)
def erp_reconcile(
    payload: ErpReconcileRequest,
    request: Request,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> ErpReconcileOut:
    """Compare PartCode items with ERP and mark matched reserved items committed."""
    try:
        adapter = get_erp_adapter()
        return reconcile_items(
            db,
            tenant_id=api_key.tenant_id,
            adapter=adapter,
            request=payload,
            actor_id=api_key.id,
            actor_type="api_key",
            ip=request.client.host if request.client else None,
        )
    except ErpConfigurationError as exc:
        raise _erp_configuration_error(exc) from exc
