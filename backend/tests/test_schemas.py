from __future__ import annotations

import pytest
from app.schemas import ErpReconcileRequest, RuleDefinition
from pydantic import ValidationError


def test_rule_definition_accepts_valid_counter_scopes() -> None:
    definition = RuleDefinition.model_validate(
        {
            "segments": [
                {
                    "type": "list",
                    "key": "family",
                    "options": [{"value": "MEC"}, {"value": "ELE"}],
                },
                {
                    "type": "counter",
                    "key": "seq",
                    "scope": "per_value",
                    "scope_keys": ["family"],
                },
            ],
            "max_length": 32,
            "case": "upper",
        }
    )
    assert definition.case == "upper"
    assert definition.max_length == 32
    assert definition.segments[1].scope == "per_value"


@pytest.mark.parametrize(
    "segments, message",
    [
        (
            [
                {"type": "list", "key": "family", "options": [{"value": "MEC"}]},
                {"type": "list", "key": "family", "options": [{"value": "ELE"}]},
            ],
            "Duplicate segment key",
        ),
        (
            [{"type": "counter", "key": "seq", "scope": "per_value"}],
            "needs scope_keys",
        ),
        (
            [{"type": "counter", "key": "seq", "scope": "per_value", "scope_keys": ["family"]}],
            "unknown or later key",
        ),
        (
            [{"type": "counter", "key": "seq"}, {"type": "counter", "key": "seq"}],
            "Duplicate counter key",
        ),
        (
            [
                {
                    "type": "text",
                    "key": "serial",
                    "regex": "[",
                }
            ],
            "Invalid regex",
        ),
        (
            [
                {
                    "type": "text",
                    "key": "serial",
                    "min_length": 5,
                    "max_length": 3,
                }
            ],
            "min_length cannot exceed max_length",
        ),
    ],
)
def test_rule_definition_rejects_invalid_constraints(segments: list[dict], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        RuleDefinition.model_validate({"segments": segments})


@pytest.mark.parametrize(
    "payload",
    [
        {"segments": []},
        {"segments": [{"type": "literal", "value": "X"}], "max_length": 0},
        {"segments": [{"type": "literal", "value": "X"}], "max_length": 129},
        {"segments": [{"type": "literal", "value": "X"}], "case": "lower"},
        {"segments": [{"type": "literal", "value": "X", "unexpected": True}]},
    ],
)
def test_rule_definition_rejects_invalid_top_level_values(
    payload: dict,
) -> None:
    with pytest.raises(ValidationError):
        RuleDefinition.model_validate(payload)


def test_erp_reconcile_request_normalizes_codes() -> None:
    request = ErpReconcileRequest(codes=["  A-1  ", "A-1", "", "B-2", "   "])
    assert request.codes == ["A-1", "B-2"]
    assert request.limit == 100
    assert request.dry_run is False


def test_erp_reconcile_request_rejects_blank_or_oversized_codes() -> None:
    with pytest.raises(ValidationError, match="at least one non-empty code"):
        ErpReconcileRequest(codes=["", "   "])
    with pytest.raises(ValidationError):
        ErpReconcileRequest(codes=[f"CODE-{index}" for index in range(201)])


@pytest.mark.parametrize("limit", [0, 201])
def test_erp_reconcile_request_enforces_limit_bounds(limit: int) -> None:
    with pytest.raises(ValidationError):
        ErpReconcileRequest(limit=limit)
