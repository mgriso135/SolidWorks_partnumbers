from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SegmentBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str | None = None
    label: str | None = None


class LiteralSegment(SegmentBase):
    type: Literal["literal"]
    value: str = Field(min_length=1, max_length=32)


class SeparatorSegment(SegmentBase):
    type: Literal["separator"]
    value: str = Field(min_length=1, max_length=8)


class ListOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=32)
    label: str | None = None


class ListSegment(SegmentBase):
    type: Literal["list"]
    key: str = Field(min_length=1, max_length=40)
    label: str | None = None
    required: bool = True
    options: list[ListOption] = Field(min_length=1, max_length=200)


class TextSegment(SegmentBase):
    type: Literal["text"]
    key: str = Field(min_length=1, max_length=40)
    label: str | None = None
    required: bool = True
    min_length: int = Field(default=0, ge=0, le=64)
    max_length: int = Field(default=32, ge=1, le=64)
    regex: str | None = None


class DateSegment(SegmentBase):
    type: Literal["date"]
    format: str = Field(default="%y", min_length=1, max_length=16)


class CounterSegment(SegmentBase):
    type: Literal["counter"]
    key: str = Field(default="seq", min_length=1, max_length=40)
    padding: int = Field(default=4, ge=1, le=12)
    start: int = Field(default=1, ge=0)
    step: int = Field(default=1, ge=1, le=1000)
    scope: Literal["rule", "per_value"] = "rule"
    scope_keys: list[str] = Field(default_factory=list)


class ChecksumSegment(SegmentBase):
    type: Literal["checksum"]
    algorithm: Literal["mod97", "luhn"] = "mod97"


Segment = Annotated[
    LiteralSegment
    | SeparatorSegment
    | ListSegment
    | TextSegment
    | DateSegment
    | CounterSegment
    | ChecksumSegment,
    Field(discriminator="type"),
]

_VALUE_SEGMENTS = (ListSegment, TextSegment)


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segments: list[Segment] = Field(min_length=1, max_length=32)
    max_length: int = Field(default=64, ge=1, le=128)
    case: Literal["upper", "preserve"] = "upper"

    @model_validator(mode="after")
    def _validate_segments(self) -> RuleDefinition:
        seen_value_keys: set[str] = set()
        seen_counter_keys: set[str] = set()
        for segment in self.segments:
            if isinstance(segment, _VALUE_SEGMENTS):
                if segment.key in seen_value_keys:
                    raise ValueError(f"Duplicate segment key '{segment.key}'")
                seen_value_keys.add(segment.key)
            if isinstance(segment, TextSegment) and segment.regex:
                try:
                    re.compile(segment.regex)
                except re.error as exc:
                    raise ValueError(f"Invalid regex for segment '{segment.key}': {exc}") from exc
            if isinstance(segment, CounterSegment):
                if segment.key in seen_counter_keys:
                    raise ValueError(f"Duplicate counter key '{segment.key}'")
                seen_counter_keys.add(segment.key)
                if segment.scope == "per_value":
                    if not segment.scope_keys:
                        raise ValueError(
                            f"Counter '{segment.key}' with scope 'per_value' needs scope_keys"
                        )
                    for scope_key in segment.scope_keys:
                        if scope_key not in seen_value_keys:
                            raise ValueError(
                                f"Counter '{segment.key}' references unknown or later key "
                                f"'{scope_key}'"
                            )
        return self


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    email: str
    role: str
    active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    document_type: str = Field(default="part", min_length=1, max_length=40)
    key: str | None = Field(default=None, max_length=80)
    status: Literal["draft", "active"] = "active"
    definition: RuleDefinition


class RuleUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    document_type: str = Field(default="part", min_length=1, max_length=40)
    status: Literal["draft", "active"] = "active"
    definition: RuleDefinition


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    key: str
    name: str
    description: str
    document_type: str
    version: int
    status: str
    definition: RuleDefinition
    created_by: str | None
    created_at: datetime


class GenerateRequest(BaseModel):
    rule_key: str = Field(min_length=1, max_length=80)
    values: dict[str, str] = Field(default_factory=dict)
    source: str = Field(default="web", max_length=32)
    external_ref: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)


class SegmentOutput(BaseModel):
    type: str
    key: str | None = None
    value: str


class GenerateOut(BaseModel):
    code: str
    rule_key: str
    rule_version: int
    item_id: str | None = None
    status: str
    segments: list[SegmentOutput]
    created_at: datetime | None = None


class ItemUpdate(BaseModel):
    external_ref: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    code: str
    rule_id: str
    rule_key: str
    rule_version: int
    status: str
    source: str
    payload: dict[str, Any]
    external_ref: str | None
    notes: str | None
    created_by: str | None
    created_at: datetime
    voided_at: datetime | None


class ItemPage(BaseModel):
    items: list[ItemOut]
    total: int
    limit: int
    offset: int


class LookupOut(BaseModel):
    exists: bool
    item: ItemOut | None = None


class ErpLookupOut(BaseModel):
    found: bool
    code: str
    adapter: str
    external_id: str | None = None
    status: str | None = None
    description: str | None = None
    message: str | None = None


class ErpReconcileRequest(BaseModel):
    codes: list[str] | None = Field(default=None, max_length=200)
    limit: int = Field(default=100, ge=1, le=200)
    dry_run: bool = False

    @field_validator("codes")
    @classmethod
    def normalize_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        codes = list(dict.fromkeys(code.strip() for code in value if code.strip()))
        if not codes:
            raise ValueError("codes must contain at least one non-empty code")
        return codes


class ErpReconcileResult(BaseModel):
    item_id: str
    code: str
    partcode_status: str
    erp_found: bool
    erp_status: str | None = None
    external_id: str | None = None
    action: Literal["matched", "committed", "would_commit", "missing", "error"]
    error: str | None = None


class ErpReconcileOut(BaseModel):
    adapter: str
    checked: int
    found: int
    not_found: int
    committed: int
    would_commit: int
    errors: int
    dry_run: bool
    results: list[ErpReconcileResult]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    role: Literal["admin", "editor", "viewer"] = "viewer"


class UserUpdate(BaseModel):
    role: Literal["admin", "editor", "viewer"] | None = None
    active: bool | None = None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prefix: str
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    key: str


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_id: str | None
    actor_type: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any]
    ip: str | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditOut]
    total: int
    limit: int
    offset: int


class DashboardStats(BaseModel):
    active_rules: int
    items_total: int
    items_30d: int
    items_today: int
    active_users: int
    by_source: dict[str, int]
    recent_items: list[ItemOut]
    recent_audit: list[AuditOut]


class MessageOut(BaseModel):
    message: str
