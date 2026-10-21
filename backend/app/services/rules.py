from __future__ import annotations

import re
import unicodedata
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Rule, User
from ..schemas import RuleCreate, RuleDefinition, RuleUpdate


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:80] or "rule"


def get_rule(db: Session, tenant_id: str, rule_id: str) -> Rule:
    rule = db.scalar(select(Rule).where(Rule.id == rule_id, Rule.tenant_id == tenant_id))
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return rule


def get_active_rule(db: Session, tenant_id: str, key: str) -> Rule:
    rule = db.scalar(
        select(Rule).where(
            Rule.tenant_id == tenant_id,
            Rule.key == key,
            Rule.status == "active",
        )
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active rule with key '{key}'",
        )
    return rule


def list_latest_rules(
    db: Session,
    tenant_id: str,
    *,
    status_filter: str | None = None,
    document_type: str | None = None,
) -> list[Rule]:
    # Pick the highest version per key, considering the requested status first.
    all_rules = db.scalars(
        select(Rule).where(Rule.tenant_id == tenant_id).order_by(Rule.name)
    ).all()
    candidates = (
        [rule for rule in all_rules if rule.status == status_filter] if status_filter else all_rules
    )
    latest: dict[str, Rule] = {}
    for rule in candidates:
        current = latest.get(rule.key)
        if current is None or rule.version > current.version:
            latest[rule.key] = rule
    result = list(latest.values())
    if document_type:
        result = [r for r in result if r.document_type == document_type]
    result.sort(key=lambda r: r.name.lower())
    return result


def list_versions(db: Session, tenant_id: str, key: str) -> list[Rule]:
    return list(
        db.scalars(
            select(Rule)
            .where(Rule.tenant_id == tenant_id, Rule.key == key)
            .order_by(Rule.version.desc())
        ).all()
    )


def _close_active_versions(db: Session, tenant_id: str, key: str, keep_id: str) -> None:
    siblings = db.scalars(
        select(Rule).where(
            Rule.tenant_id == tenant_id,
            Rule.key == key,
            Rule.status == "active",
            Rule.id != keep_id,
        )
    ).all()
    for sibling in siblings:
        sibling.status = "archived"


def create_rule(db: Session, tenant_id: str, author: User, payload: RuleCreate) -> Rule:
    key = slugify(payload.key or payload.name)
    existing = db.scalar(select(Rule).where(Rule.tenant_id == tenant_id, Rule.key == key))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A rule with key '{key}' already exists",
        )
    rule = Rule(
        tenant_id=tenant_id,
        key=key,
        name=payload.name,
        description=payload.description,
        document_type=payload.document_type,
        version=1,
        status=payload.status,
        definition=payload.definition.model_dump(),
        created_by=author.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, tenant_id: str, rule: Rule, payload: RuleUpdate, author: User) -> Rule:
    latest = db.scalar(
        select(Rule)
        .where(Rule.tenant_id == tenant_id, Rule.key == rule.key)
        .order_by(Rule.version.desc())
    )
    next_version = (latest.version if latest else rule.version) + 1
    new_rule = Rule(
        tenant_id=tenant_id,
        key=rule.key,
        name=payload.name,
        description=payload.description,
        document_type=payload.document_type,
        version=next_version,
        status=payload.status,
        definition=payload.definition.model_dump(),
        created_by=author.id,
    )
    db.add(new_rule)
    db.flush()
    if payload.status == "active":
        _close_active_versions(db, tenant_id, rule.key, new_rule.id)
    elif rule.status == "draft":
        rule.status = "archived"
    db.commit()
    db.refresh(new_rule)
    return new_rule


def archive_rule(db: Session, rule: Rule) -> Rule:
    rule.status = "archived"
    db.commit()
    db.refresh(rule)
    return rule


def rule_definition(rule: Rule) -> RuleDefinition:
    return RuleDefinition.model_validate(rule.definition)


def definition_dict(rule: Rule) -> dict[str, Any]:
    return dict(rule.definition)
