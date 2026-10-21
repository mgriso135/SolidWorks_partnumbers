from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .base import ErpAdapter, ErpAdapterError, ErpItem


class RestErpAdapter(ErpAdapter):
    """Generic JSON-over-HTTP ERP adapter.

    The lookup URL is ``base_url + lookup_path`` where ``lookup_path`` must
    contain a ``{code}`` placeholder. A ``404`` means "not found". Other HTTP or
    transport failures are surfaced as ``ErpAdapterError``.
    """

    name = "rest"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        api_key_header: str = "Authorization",
        api_key_prefix: str = "Bearer ",
        lookup_path: str = "/items/{code}",
        propose_path: str = "/items",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.api_key_prefix = api_key_prefix
        self.lookup_path = lookup_path
        self.propose_path = propose_path
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        if self.api_key:
            headers[self.api_key_header] = f"{self.api_key_prefix}{self.api_key}"
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self._transport,
            ) as client:
                return client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ErpAdapterError(f"ERP request failed: {exc}") from exc

    def lookup(self, code: str) -> ErpItem | None:
        path = self.lookup_path.format(code=quote(code.strip(), safe=""))
        response = self._request("GET", path)
        if response.status_code == 404:
            return None
        if response.is_error:
            raise ErpAdapterError(
                f"ERP lookup failed with HTTP {response.status_code}: {response.text[:200]}"
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            data = response.json()
        except ValueError as exc:
            raise ErpAdapterError("ERP returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ErpAdapterError("ERP lookup must return a JSON object")
        if data.get("found") is False:
            return None

        external_id = data.get("external_id") or data.get("id")
        return ErpItem(
            code=str(data.get("code") or code),
            external_id=str(external_id) if external_id is not None else None,
            status=str(data["status"]) if data.get("status") is not None else None,
            description=(str(data["description"]) if data.get("description") is not None else None),
            raw=data,
        )

    def propose_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", self.propose_path, json=payload)
        if response.is_error:
            raise ErpAdapterError(
                f"ERP item creation failed with HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ErpAdapterError("ERP returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ErpAdapterError("ERP item creation must return a JSON object")
        return data
