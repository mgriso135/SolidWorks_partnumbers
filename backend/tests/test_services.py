from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.schemas import RuleDefinition
from app.services import generator
from app.services import rules as rule_service
from app.services.errors import GenerationError


def definition(payload: dict) -> RuleDefinition:
    return RuleDefinition.model_validate(payload)


def test_checksum_algorithms_have_known_outputs() -> None:
    assert generator._mod97("ABC") == "79"
    assert generator._luhn("123") == "0"
    assert generator._luhn("ABC") == "5"
    assert generator._checksum("ABC", "mod97") == "79"
    assert generator._checksum("ABC", "luhn") == "5"
    assert generator._char_value("!") == 0
    assert generator._char_value("z") == 35


def test_validate_values_normalizes_lists_and_text() -> None:
    rule_definition = definition(
        {
            "segments": [
                {
                    "type": "list",
                    "key": "family",
                    "options": [{"value": "MEC"}, {"value": "ELE"}],
                },
                {
                    "type": "text",
                    "key": "serial",
                    "min_length": 3,
                    "max_length": 5,
                    "regex": "^[0-9]+$",
                },
            ]
        }
    )
    normalized = generator.validate_values(
        rule_definition,
        {"family": " mec ", "serial": " 123 ", "ignored": "value"},
    )
    assert normalized == {"family": "MEC", "serial": "123"}


def test_validate_values_collects_all_field_errors() -> None:
    rule_definition = definition(
        {
            "segments": [
                {
                    "type": "list",
                    "key": "family",
                    "options": [{"value": "MEC"}, {"value": "ELE"}],
                },
                {
                    "type": "text",
                    "key": "serial",
                    "min_length": 3,
                    "max_length": 5,
                    "regex": "^[0-9]+$",
                },
            ]
        }
    )
    with pytest.raises(GenerationError) as exc_info:
        generator.validate_values(rule_definition, {"family": "XYZ", "serial": "12"})

    error = exc_info.value
    assert error.code == "INVALID_INPUT"
    assert error.status_code == 422
    assert set(error.fields) == {"family", "serial"}
    assert error.fields["family"] == "Must be one of: MEC, ELE"
    assert error.fields["serial"] == "Must be at least 3 characters"

    with pytest.raises(GenerationError) as regex_error:
        generator.validate_values(rule_definition, {"family": "MEC", "serial": "abc"})
    assert regex_error.value.fields["serial"] == "Does not match the required format"


def test_optional_values_can_be_omitted() -> None:
    rule_definition = definition(
        {
            "segments": [
                {
                    "type": "list",
                    "key": "family",
                    "required": False,
                    "options": [{"value": "MEC"}],
                },
                {
                    "type": "text",
                    "key": "serial",
                    "required": False,
                    "min_length": 3,
                },
            ]
        }
    )
    assert generator.validate_values(rule_definition, {}) == {}


def test_scope_keys_are_stable_for_rule_and_per_value() -> None:
    rule_scope = definition(
        {
            "segments": [
                {"type": "counter", "key": "seq", "scope": "rule"},
            ]
        }
    ).segments[0]
    per_value = definition(
        {
            "segments": [
                {"type": "list", "key": "family", "options": [{"value": "MEC"}]},
                {"type": "list", "key": "region", "options": [{"value": "EU"}]},
                {
                    "type": "counter",
                    "key": "seq",
                    "scope": "per_value",
                    "scope_keys": ["family", "region"],
                },
            ]
        }
    ).segments[2]

    assert generator._scope_key(rule_scope, {}) == "seq:"
    assert generator._scope_key(per_value, {"family": "MEC", "region": "EU"}) == (
        "seq:family=MEC|region=EU"
    )
    assert generator._scope_key(per_value, {}) == "seq:family=|region="


def test_render_applies_case_padding_and_date() -> None:
    rule_definition = definition(
        {
            "segments": [
                {"type": "literal", "value": "prt"},
                {"type": "separator", "value": "-"},
                {"type": "list", "key": "family", "options": [{"value": "mec"}]},
                {"type": "separator", "value": "-"},
                {"type": "date", "format": "%Y"},
                {"type": "separator", "value": "-"},
                {"type": "counter", "key": "seq", "padding": 4},
            ],
            "case": "upper",
        }
    )
    rendered = generator._render(
        rule_definition,
        {"family": "mec"},
        {"seq": 7},
        datetime(2026, 10, 21, tzinfo=UTC),
    )

    assert rendered.code == "PRT-MEC-2026-0007"
    assert [segment["value"] for segment in rendered.segments] == [
        "PRT",
        "-",
        "MEC",
        "-",
        "2026",
        "-",
        "0007",
    ]


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"segments": [{"type": "literal", "value": "AbC"}], "case": "preserve"}, "AbC"),
        ({"segments": [{"type": "literal", "value": "AbC"}], "case": "upper"}, "ABC"),
        (
            {
                "segments": [
                    {"type": "literal", "value": "ABC"},
                    {"type": "checksum", "algorithm": "mod97"},
                ]
            },
            "ABC79",
        ),
        (
            {
                "segments": [
                    {"type": "literal", "value": "123"},
                    {"type": "checksum", "algorithm": "luhn"},
                ]
            },
            "1230",
        ),
    ],
)
def test_render_supports_case_and_checksums(payload: dict, expected: str) -> None:
    rule_definition = definition(payload)
    rendered = generator._render(rule_definition, {}, {}, datetime(2026, 1, 1, tzinfo=UTC))
    assert rendered.code == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("  PDM:123  ", "PDM:123"),
        ("PDM:123", "PDM:123"),
    ],
)
def test_normalize_external_ref(value: str | None, expected: str | None) -> None:
    assert generator.normalize_external_ref(value) == expected


def test_generation_error_detail_defaults() -> None:
    error = GenerationError("BAD", "Something went wrong")
    assert error.status_code == 422
    assert error.as_detail() == {
        "code": "BAD",
        "message": "Something went wrong",
        "fields": {},
    }


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Mechanical Part", "mechanical-part"),
        ("  ---  ", "rule"),
        ("Überprüfung", "uberprufung"),
        ("A/B_C", "a-b-c"),
        ("x" * 100, "x" * 80),
    ],
)
def test_slugify(value: str, expected: str) -> None:
    assert rule_service.slugify(value) == expected
