from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ErpError(Exception):
    """Base class for ERP adapter failures."""


class ErpAdapterError(ErpError):
    """The ERP system could not answer a request."""


class ErpConfigurationError(ErpError):
    """The ERP adapter is missing required configuration."""


@dataclass(frozen=True)
class ErpItem:
    code: str
    external_id: str | None = None
    status: str | None = None
    description: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class ErpAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def lookup(self, code: str) -> ErpItem | None:
        """Return the ERP item for a PartCode code, or None when it is absent."""

    def exists(self, code: str) -> bool:
        return self.lookup(code) is not None

    def propose_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise ErpAdapterError(f"The {self.name} ERP adapter does not support item creation")
