from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Store naive UTC in SQLite and return timezone-aware UTC values."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", "version", name="uq_rules_tenant_key_version"),
        Index("ix_rules_tenant_key_status", "tenant_id", "key", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, default="part")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Counter(Base):
    __tablename__ = "counters"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "rule_key", "scope_key", name="uq_counters_tenant_rule_scope"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_items_tenant_code"),
        Index("ix_items_tenant_created", "tenant_id", "created_at"),
        Index("ix_items_tenant_external_ref", "tenant_id", "external_ref"),
        Index(
            "uq_items_tenant_external_ref_active",
            "tenant_id",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref IS NOT NULL AND status <> 'void'"),
            sqlite_where=text("external_ref IS NOT NULL AND status <> 'void'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("rules.id", ondelete="RESTRICT"), nullable=False
    )
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="reserved")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    external_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    voided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
