from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    cors_origins: tuple[str, ...]
    seed_demo: bool
    auto_create_tables: bool
    environment: str
    erp_adapter: str = "stub"
    erp_base_url: str | None = None
    erp_api_key: str | None = None
    erp_api_key_header: str = "Authorization"
    erp_api_key_prefix: str = "Bearer "
    erp_lookup_path: str = "/items/{code}"
    erp_file_path: str | None = None
    erp_timeout_seconds: float = 10.0


def _load_settings() -> Settings:
    origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000",
    )
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./partcode.db"),
        jwt_secret=os.getenv("JWT_SECRET", "dev-only-change-me"),
        jwt_algorithm="HS256",
        jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "720")),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        seed_demo=_as_bool(os.getenv("SEED_DEMO"), True),
        auto_create_tables=_as_bool(os.getenv("AUTO_CREATE_TABLES"), True),
        environment=os.getenv("ENVIRONMENT", "development"),
        erp_adapter=os.getenv("ERP_ADAPTER", "stub"),
        erp_base_url=os.getenv("ERP_BASE_URL") or None,
        erp_api_key=os.getenv("ERP_API_KEY") or None,
        erp_api_key_header=os.getenv("ERP_API_KEY_HEADER", "Authorization"),
        erp_api_key_prefix=os.getenv("ERP_API_KEY_PREFIX", "Bearer "),
        erp_lookup_path=os.getenv("ERP_LOOKUP_PATH", "/items/{code}"),
        erp_file_path=os.getenv("ERP_FILE_PATH") or None,
        erp_timeout_seconds=float(os.getenv("ERP_TIMEOUT_SECONDS", "10")),
    )


settings = _load_settings()
