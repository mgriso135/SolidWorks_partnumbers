from __future__ import annotations

from ...config import Settings, settings
from .base import ErpAdapter, ErpConfigurationError
from .file import FileErpAdapter
from .rest import RestErpAdapter
from .stub import StubErpAdapter


def build_erp_adapter(config: Settings | None = None) -> ErpAdapter:
    config = config or settings
    name = config.erp_adapter.strip().lower()
    if name == "stub":
        return StubErpAdapter()
    if name == "file":
        if not config.erp_file_path:
            raise ErpConfigurationError("ERP_FILE_PATH is required for the file adapter")
        return FileErpAdapter(config.erp_file_path)
    if name == "rest":
        if not config.erp_base_url:
            raise ErpConfigurationError("ERP_BASE_URL is required for the REST adapter")
        if "{code}" not in config.erp_lookup_path:
            raise ErpConfigurationError("ERP_LOOKUP_PATH must contain the {code} placeholder")
        return RestErpAdapter(
            base_url=config.erp_base_url,
            api_key=config.erp_api_key,
            api_key_header=config.erp_api_key_header,
            api_key_prefix=config.erp_api_key_prefix,
            lookup_path=config.erp_lookup_path,
            timeout_seconds=config.erp_timeout_seconds,
        )
    raise ErpConfigurationError(
        f"Unsupported ERP_ADAPTER={config.erp_adapter!r}; use stub, file, or rest"
    )
