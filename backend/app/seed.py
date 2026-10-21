from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Item, Rule, Tenant, User
from .schemas import GenerateRequest, RuleDefinition
from .security import hash_password
from .services import generator


def _definition(payload: dict) -> dict:
    return RuleDefinition.model_validate(payload).model_dump()


def _rule(
    *,
    tenant_id: str,
    key: str,
    name: str,
    description: str,
    document_type: str,
    definition: dict,
    created_by: str,
) -> Rule:
    return Rule(
        tenant_id=tenant_id,
        key=key,
        name=name,
        description=description,
        document_type=document_type,
        version=1,
        status="active",
        definition=_definition(definition),
        created_by=created_by,
    )


def seed_demo_data(db: Session) -> None:
    existing = db.scalar(select(func.count(User.id)))
    if existing:
        return

    tenant = Tenant(name="Demo Company", slug="demo")
    db.add(tenant)
    db.flush()

    admin = User(
        tenant_id=tenant.id,
        email="admin@demo.local",
        password_hash=hash_password("Admin123!"),
        role="admin",
    )
    editor = User(
        tenant_id=tenant.id,
        email="editor@demo.local",
        password_hash=hash_password("Editor123!"),
        role="editor",
    )
    viewer = User(
        tenant_id=tenant.id,
        email="viewer@demo.local",
        password_hash=hash_password("Viewer123!"),
        role="viewer",
    )
    db.add_all([admin, editor, viewer])
    db.flush()

    family_options = [
        {"value": "MEC", "label": "Mechanical"},
        {"value": "ELE", "label": "Electrical"},
        {"value": "PNE", "label": "Pneumatic"},
    ]

    rules = [
        _rule(
            tenant_id=tenant.id,
            key="mechanical-part",
            name="Mechanical part",
            description="Part number: PRT-<family>-<progressive>",
            document_type="part",
            created_by=admin.id,
            definition={
                "segments": [
                    {"type": "literal", "value": "PRT"},
                    {"type": "separator", "value": "-"},
                    {
                        "type": "list",
                        "key": "family",
                        "label": "Family",
                        "required": True,
                        "options": family_options,
                    },
                    {"type": "separator", "value": "-"},
                    {
                        "type": "counter",
                        "key": "seq",
                        "padding": 5,
                        "start": 1,
                        "step": 1,
                        "scope": "per_value",
                        "scope_keys": ["family"],
                    },
                ],
                "max_length": 32,
                "case": "upper",
            },
        ),
        _rule(
            tenant_id=tenant.id,
            key="technical-drawing",
            name="Technical drawing",
            description="Drawing number: DRW-<family>-<yy>-<progressive>",
            document_type="drawing",
            created_by=admin.id,
            definition={
                "segments": [
                    {"type": "literal", "value": "DRW"},
                    {"type": "separator", "value": "-"},
                    {
                        "type": "list",
                        "key": "family",
                        "label": "Family",
                        "required": True,
                        "options": family_options,
                    },
                    {"type": "separator", "value": "-"},
                    {"type": "date", "format": "%y"},
                    {"type": "separator", "value": "-"},
                    {
                        "type": "counter",
                        "key": "seq",
                        "padding": 4,
                        "start": 1,
                        "step": 1,
                        "scope": "per_value",
                        "scope_keys": ["family"],
                    },
                ],
                "max_length": 32,
                "case": "upper",
            },
        ),
        _rule(
            tenant_id=tenant.id,
            key="assembly",
            name="Assembly",
            description="Assembly number: ASM-<family>-<progressive>",
            document_type="assembly",
            created_by=admin.id,
            definition={
                "segments": [
                    {"type": "literal", "value": "ASM"},
                    {"type": "separator", "value": "-"},
                    {
                        "type": "list",
                        "key": "family",
                        "label": "Family",
                        "required": True,
                        "options": family_options,
                    },
                    {"type": "separator", "value": "-"},
                    {
                        "type": "counter",
                        "key": "seq",
                        "padding": 4,
                        "start": 1,
                        "step": 1,
                        "scope": "per_value",
                        "scope_keys": ["family"],
                    },
                ],
                "max_length": 32,
                "case": "upper",
            },
        ),
    ]
    db.add_all(rules)
    db.flush()

    db.commit()

    samples = [
        ("mechanical-part", {"family": "MEC"}, "BRACKET-001"),
        ("mechanical-part", {"family": "ELE"}, "CONTROL-BOX"),
        ("mechanical-part", {"family": "MEC"}, "SHAFT-ADAPTER"),
        ("technical-drawing", {"family": "MEC"}, "BRACKET-001-DWG"),
        ("assembly", {"family": "MEC"}, "MAIN-ASSEMBLY"),
    ]
    for rule_key, values, external_ref in samples:
        rule = db.scalar(
            select(Rule).where(
                Rule.tenant_id == tenant.id,
                Rule.key == rule_key,
                Rule.status == "active",
            )
        )
        if rule is None:
            continue
        request = GenerateRequest(
            rule_key=rule_key,
            values=values,
            source="seed",
            external_ref=external_ref,
            metadata={
                "description": external_ref.replace("-", " ").title(),
            },
        )
        generator.commit_code(
            db,
            tenant_id=tenant.id,
            rule=rule,
            request=request,
            created_by=admin.id,
        )

    existing_items = db.scalar(select(func.count(Item.id)).where(Item.tenant_id == tenant.id))
    assert existing_items == len(samples)
