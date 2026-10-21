from __future__ import annotations

import hashlib

import jwt
import pytest
from app.config import _as_bool
from app.security import (
    create_access_token,
    decode_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip_and_rejection() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("scrypt$")
    assert verify_password("correct horse battery staple", encoded) is True
    assert verify_password("wrong password", encoded) is False
    assert verify_password("anything", "not-a-hash") is False
    assert verify_password("anything", "argon2$1$2$3$4$5") is False


def test_access_token_roundtrip() -> None:
    token = create_access_token(user_id="user-1", tenant_id="tenant-1", role="editor")
    payload = decode_token(token)

    assert payload["sub"] == "user-1"
    assert payload["tid"] == "tenant-1"
    assert payload["role"] == "editor"
    assert payload["exp"] > payload["iat"]


def test_decode_token_rejects_invalid_tokens() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_token("not-a-jwt")


def test_api_key_generation_is_hashed_and_prefixed() -> None:
    secret, prefix, digest = generate_api_key()

    assert secret.startswith("pk_live_")
    assert prefix == secret[:12]
    assert len(digest) == 64
    assert digest == hash_api_key(secret)
    assert digest == hashlib.sha256(secret.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("anything-else", False),
    ],
)
def test_as_bool(value: str, expected: bool) -> None:
    assert _as_bool(value, default=not expected) is expected
