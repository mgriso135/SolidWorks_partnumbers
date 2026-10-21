from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Counter, Item, Rule, utcnow
from ..schemas import (
    ChecksumSegment,
    CounterSegment,
    DateSegment,
    GenerateRequest,
    ListSegment,
    RuleDefinition,
    SeparatorSegment,
    TextSegment,
)
from .errors import GenerationError

_VALUE_TYPES = (ListSegment, TextSegment)
_COUNTER_TYPES = (CounterSegment,)


@dataclass
class Rendered:
    code: str
    segments: list[dict[str, Any]]


def _char_value(char: str) -> int:
    try:
        return int(char, 36)
    except ValueError:
        return 0


def _mod97(payload: str) -> str:
    acc = 0
    for char in payload.upper():
        acc = (acc * 36 + _char_value(char)) % 97
    return f"{acc:02d}"


def _luhn(payload: str) -> str:
    digits = [_char_value(char) % 10 for char in payload.upper()]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def _checksum(payload: str, algorithm: str) -> str:
    return _mod97(payload) if algorithm == "mod97" else _luhn(payload)


def validate_values(definition: RuleDefinition, values: dict[str, str]) -> dict[str, str]:
    """Validate user-supplied values and return canonical values."""
    normalized: dict[str, str] = {}
    errors: dict[str, str] = {}

    for segment in definition.segments:
        if isinstance(segment, ListSegment):
            raw = (values.get(segment.key) or "").strip()
            if not raw:
                if segment.required:
                    errors[segment.key] = "This field is required"
                continue
            match = next(
                (
                    option
                    for option in segment.options
                    if option.value == raw or option.value.lower() == raw.lower()
                ),
                None,
            )
            if match is None:
                allowed = ", ".join(option.value for option in segment.options)
                errors[segment.key] = f"Must be one of: {allowed}"
            else:
                normalized[segment.key] = match.value
        elif isinstance(segment, TextSegment):
            raw = (values.get(segment.key) or "").strip()
            if not raw:
                if segment.required:
                    errors[segment.key] = "This field is required"
                continue
            if len(raw) < segment.min_length:
                errors[segment.key] = f"Must be at least {segment.min_length} characters"
            elif len(raw) > segment.max_length:
                errors[segment.key] = f"Must be at most {segment.max_length} characters"
            elif segment.regex and re.fullmatch(segment.regex, raw) is None:
                errors[segment.key] = "Does not match the required format"
            else:
                normalized[segment.key] = raw

    if errors:
        raise GenerationError("INVALID_INPUT", "Some fields are invalid", fields=errors)
    return normalized


def _scope_key(segment: CounterSegment, normalized: dict[str, str]) -> str:
    if segment.scope == "rule":
        return f"{segment.key}:"
    parts = [f"{key}={normalized.get(key, '')}" for key in segment.scope_keys]
    return f"{segment.key}:{'|'.join(parts)}"


def _counter_value_preview(
    db: Session, tenant_id: str, rule_key: str, segment: CounterSegment, scope_key: str
) -> int:
    current = db.scalar(
        select(Counter.value).where(
            Counter.tenant_id == tenant_id,
            Counter.rule_key == rule_key,
            Counter.scope_key == scope_key,
        )
    )
    if current is None:
        return segment.start
    return int(current) + segment.step


def _counter_value_reserve(
    db: Session,
    tenant_id: str,
    rule_key: str,
    segment: CounterSegment,
    scope_key: str,
) -> int:
    statement = text(
        """
        INSERT INTO counters (id, tenant_id, rule_key, scope_key, value, updated_at)
        VALUES (:id, :tenant_id, :rule_key, :scope_key, :start, :now)
        ON CONFLICT (tenant_id, rule_key, scope_key)
        DO UPDATE SET value = counters.value + :step, updated_at = :now
        RETURNING value
        """
    )
    value = db.execute(
        statement,
        {
            "id": uuid.uuid4().hex,
            "tenant_id": tenant_id,
            "rule_key": rule_key,
            "scope_key": scope_key,
            "start": segment.start,
            "step": segment.step,
            "now": utcnow(),
        },
    ).scalar_one()
    return int(value)


def _render(
    definition: RuleDefinition,
    normalized: dict[str, str],
    counter_values: dict[str, int],
    moment: datetime,
) -> Rendered:
    parts: list[str] = []
    segments: list[dict[str, Any]] = []
    uppercase = definition.case == "upper"

    for segment in definition.segments:
        key: str | None = getattr(segment, "key", None)
        if isinstance(segment, SeparatorSegment):
            raw = segment.value
        elif isinstance(segment, ListSegment | TextSegment):
            raw = normalized.get(segment.key, "")
        elif isinstance(segment, DateSegment):
            raw = moment.strftime(segment.format)
        elif isinstance(segment, CounterSegment):
            raw = str(counter_values.get(segment.key, segment.start)).zfill(segment.padding)
        elif isinstance(segment, ChecksumSegment):
            raw = _checksum("".join(parts), segment.algorithm)
        else:
            raw = getattr(segment, "value", "")

        if uppercase:
            raw = raw.upper()
        parts.append(raw)
        segments.append({"type": segment.type, "key": key, "value": raw})

    code = "".join(parts)
    if not code.strip():
        raise GenerationError(
            "EMPTY_CODE",
            "The rule produced an empty code",
            fields={"code": ""},
        )
    return Rendered(code=code, segments=segments)


def preview_code(db: Session, *, tenant_id: str, rule: Rule, request: GenerateRequest) -> Rendered:
    definition = RuleDefinition.model_validate(rule.definition)
    normalized = validate_values(definition, request.values)
    counter_values: dict[str, int] = {}
    for segment in definition.segments:
        if isinstance(segment, CounterSegment):
            scope_key = _scope_key(segment, normalized)
            counter_values[segment.key] = _counter_value_preview(
                db, tenant_id, rule.key, segment, scope_key
            )
    rendered = _render(definition, normalized, counter_values, datetime.now(UTC))
    if len(rendered.code) > definition.max_length:
        raise GenerationError(
            "CODE_TOO_LONG",
            f"Generated code exceeds {definition.max_length} characters",
            fields={"code": rendered.code},
        )
    return rendered


def normalize_external_ref(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def ensure_external_ref_available(
    db: Session,
    *,
    tenant_id: str,
    external_ref: str | None,
    exclude_item_id: str | None = None,
) -> None:
    normalized = normalize_external_ref(external_ref)
    if not normalized:
        return
    query = select(Item).where(
        Item.tenant_id == tenant_id,
        Item.external_ref == normalized,
        Item.status != "void",
    )
    if exclude_item_id is not None:
        query = query.where(Item.id != exclude_item_id)
    duplicate = db.scalar(query)
    if duplicate is not None:
        raise GenerationError(
            "DUPLICATE_EXTERNAL_REF",
            (
                "An item already exists for this external reference: "
                f"{normalized} (code {duplicate.code})"
            ),
            fields={
                "external_ref": normalized,
                "code": duplicate.code,
                "item_id": duplicate.id,
            },
            status_code=409,
        )


def commit_code(
    db: Session,
    *,
    tenant_id: str,
    rule: Rule,
    request: GenerateRequest,
    created_by: str | None,
) -> tuple[Item, list[dict[str, Any]]]:
    definition = RuleDefinition.model_validate(rule.definition)
    normalized = validate_values(definition, request.values)
    external_ref = normalize_external_ref(request.external_ref)
    ensure_external_ref_available(
        db,
        tenant_id=tenant_id,
        external_ref=external_ref,
    )

    last_error: Exception | None = None
    for _attempt in range(5):
        try:
            counter_values: dict[str, int] = {}
            for segment in definition.segments:
                if isinstance(segment, CounterSegment):
                    scope_key = _scope_key(segment, normalized)
                    counter_values[segment.key] = _counter_value_reserve(
                        db, tenant_id, rule.key, segment, scope_key
                    )

            rendered = _render(definition, normalized, counter_values, datetime.now(UTC))
            if len(rendered.code) > definition.max_length:
                db.rollback()
                raise GenerationError(
                    "CODE_TOO_LONG",
                    f"Generated code exceeds {definition.max_length} characters",
                    fields={"code": rendered.code},
                )

            payload: dict[str, Any] = {**request.metadata, **normalized}
            item = Item(
                tenant_id=tenant_id,
                code=rendered.code,
                rule_id=rule.id,
                rule_key=rule.key,
                rule_version=rule.version,
                status="reserved",
                source=request.source,
                payload=payload,
                external_ref=external_ref,
                notes=request.notes,
                created_by=created_by,
            )
            try:
                # Keep the counter reservation when the item insert collides, so
                # the next attempt reserves the following counter value.
                with db.begin_nested():
                    db.add(item)
                    db.flush()
            except IntegrityError as exc:
                last_error = exc
                if external_ref:
                    ensure_external_ref_available(
                        db,
                        tenant_id=tenant_id,
                        external_ref=external_ref,
                    )
                continue
            db.commit()
            db.refresh(item)
            return item, rendered.segments
        except IntegrityError as exc:
            last_error = exc
            db.rollback()
            if external_ref:
                ensure_external_ref_available(
                    db,
                    tenant_id=tenant_id,
                    external_ref=external_ref,
                )
            continue

    raise GenerationError(
        "CONFLICT",
        "Could not allocate a unique code after several attempts",
        status_code=409,
    ) from last_error
