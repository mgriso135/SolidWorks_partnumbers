from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .base import ErpAdapter, ErpAdapterError, ErpConfigurationError, ErpItem


class FileErpAdapter(ErpAdapter):
    """Read-only ERP snapshot from a JSON or CSV file.

    JSON accepts a list of item objects, an object with an ``items`` list, or a
    mapping of code to item object. CSV requires a ``code`` column; ``id``,
    ``external_id``, ``status``, and ``description`` are optional.
    """

    name = "file"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            raise ErpConfigurationError(f"ERP file not found: {self.path}")

        try:
            if self.path.suffix.lower() == ".csv":
                with self.path.open(newline="", encoding="utf-8") as handle:
                    return [dict(row) for row in csv.DictReader(handle)]
            with self.path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ErpAdapterError(f"Could not read ERP file {self.path}: {exc}") from exc

        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                return [row for row in items if isinstance(row, dict)]
            return [{"code": code, **row} for code, row in data.items() if isinstance(row, dict)]
        raise ErpAdapterError("ERP JSON must contain a list or an object of items")

    def lookup(self, code: str) -> ErpItem | None:
        needle = code.strip().upper()
        for row in self._rows():
            row_code = str(row.get("code") or row.get("Code") or "").strip()
            if not row_code or row_code.upper() != needle:
                continue
            external_id = row.get("external_id") or row.get("id")
            return ErpItem(
                code=row_code,
                external_id=str(external_id) if external_id is not None else None,
                status=str(row["status"]) if row.get("status") is not None else None,
                description=(
                    str(row["description"]) if row.get("description") is not None else None
                ),
                raw=row,
            )
        return None

    def propose_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise ErpAdapterError("The file ERP adapter is read-only")
