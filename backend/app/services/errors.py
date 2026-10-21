from __future__ import annotations

from typing import Any


class GenerationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        fields: dict[str, str] | None = None,
        status_code: int = 422,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = fields or {}
        self.status_code = status_code

    def as_detail(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "fields": self.fields}
