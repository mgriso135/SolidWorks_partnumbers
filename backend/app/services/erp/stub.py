from __future__ import annotations

from .base import ErpAdapter, ErpAdapterError, ErpItem


class StubErpAdapter(ErpAdapter):
    """In-memory adapter used when no real ERP is configured."""

    name = "stub"

    def __init__(self, items: dict[str, ErpItem] | None = None) -> None:
        self._items = {
            code.strip().upper(): item for code, item in (items or {}).items() if code.strip()
        }

    def lookup(self, code: str) -> ErpItem | None:
        return self._items.get(code.strip().upper())

    def propose_item(self, payload: dict[str, object]) -> dict[str, object]:
        raise ErpAdapterError("The stub ERP adapter is read-only")
