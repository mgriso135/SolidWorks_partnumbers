from __future__ import annotations

import json
import uuid
from dataclasses import replace

import httpx
import pytest
from app.api import integrations
from app.config import settings
from app.services.erp import (
    ErpAdapterError,
    ErpConfigurationError,
    ErpItem,
    FileErpAdapter,
    RestErpAdapter,
    build_erp_adapter,
)
from fastapi.testclient import TestClient

from .test_api import make_rule


def erp_key(client: TestClient, admin_headers: dict[str, str]) -> dict[str, str]:
    response = client.post(
        "/api/admin/api-keys",
        json={"name": f"ERP test {uuid.uuid4().hex[:8]}"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return {"X-API-Key": response.json()["key"]}


def test_file_erp_adapter_json_and_csv(tmp_path) -> None:
    json_path = tmp_path / "erp.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "code": "PRT-MEC-00001",
                    "id": "ERP-1",
                    "status": "released",
                    "description": "Bracket",
                }
            ]
        ),
        encoding="utf-8",
    )
    adapter = FileErpAdapter(json_path)
    found = adapter.lookup(" prt-mec-00001 ")
    assert found is not None
    assert found.code == "PRT-MEC-00001"
    assert found.external_id == "ERP-1"
    assert found.status == "released"
    assert found.description == "Bracket"
    assert adapter.exists("PRT-MEC-00001")
    assert adapter.lookup("missing") is None

    csv_path = tmp_path / "erp.csv"
    csv_path.write_text(
        "code,external_id,status\nPRT-ELE-00002,ERP-2,released\n",
        encoding="utf-8",
    )
    csv_adapter = FileErpAdapter(csv_path)
    csv_item = csv_adapter.lookup("PRT-ELE-00002")
    assert csv_item is not None
    assert csv_item.external_id == "ERP-2"


def test_rest_erp_adapter_lookup_and_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        if request.url.path == "/items/PRT-MEC-00001":
            return httpx.Response(
                200,
                json={
                    "code": "PRT-MEC-00001",
                    "id": "ERP-1",
                    "status": "released",
                    "description": "Bracket",
                },
            )
        if request.url.path == "/items/boom":
            return httpx.Response(500, text="boom")
        return httpx.Response(404)

    adapter = RestErpAdapter(
        base_url="https://erp.example",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )
    found = adapter.lookup("PRT-MEC-00001")
    assert found is not None
    assert found.external_id == "ERP-1"
    assert adapter.lookup("missing") is None
    with pytest.raises(ErpAdapterError):
        adapter.lookup("boom")


def test_rest_adapter_requires_code_placeholder() -> None:
    config = replace(
        settings,
        erp_adapter="rest",
        erp_base_url="https://erp.example",
        erp_lookup_path="/items",
    )
    with pytest.raises(ErpConfigurationError, match="placeholder"):
        build_erp_adapter(config)


class FakeErpAdapter:
    name = "fake"

    def __init__(self, known: set[str]) -> None:
        self.known = known

    def lookup(self, code: str) -> ErpItem | None:
        if code not in self.known:
            return None
        return ErpItem(
            code=code,
            external_id="ERP-" + code[-5:],
            status="released",
            description="ERP item",
        )


def test_erp_lookup_and_reconcile(
    client: TestClient,
    admin_headers: dict[str, str],
    editor_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = make_rule(client, editor_headers)
    generated = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"family": "MEC"}},
        headers=editor_headers,
    )
    assert generated.status_code == 200, generated.text
    code = generated.json()["code"]
    item_id = generated.json()["item_id"]

    monkeypatch.setattr(integrations, "get_erp_adapter", lambda: FakeErpAdapter({code}))
    headers = erp_key(client, admin_headers)

    lookup = client.get(
        "/api/integrations/erp/lookup",
        params={"code": code},
        headers=headers,
    )
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["found"] is True
    assert lookup.json()["adapter"] == "fake"
    assert lookup.json()["external_id"].startswith("ERP-")

    missing = client.get(
        "/api/integrations/erp/lookup",
        params={"code": "NOPE-NOT-IN-ERP"},
        headers=headers,
    )
    assert missing.status_code == 200
    assert missing.json()["found"] is False

    dry_run = client.post(
        "/api/integrations/erp/reconcile",
        json={"codes": [code], "dry_run": True},
        headers=headers,
    )
    assert dry_run.status_code == 200, dry_run.text
    assert dry_run.json()["would_commit"] == 1
    assert dry_run.json()["committed"] == 0
    assert dry_run.json()["results"][0]["action"] == "would_commit"

    item_before = client.get(f"/api/items/{item_id}", headers=admin_headers).json()
    assert item_before["status"] == "reserved"

    reconciled = client.post(
        "/api/integrations/erp/reconcile",
        json={"codes": [code]},
        headers=headers,
    )
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["committed"] == 1
    assert reconciled.json()["results"][0]["action"] == "committed"

    item_after = client.get(f"/api/items/{item_id}", headers=admin_headers).json()
    assert item_after["status"] == "committed"

    again = client.post(
        "/api/integrations/erp/reconcile",
        json={"codes": [code]},
        headers=headers,
    )
    assert again.status_code == 200
    assert again.json()["committed"] == 0
    assert again.json()["results"][0]["action"] == "matched"

    audit = client.get(
        "/api/admin/audit",
        params={"action": "item.committed"},
        headers=admin_headers,
    )
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1


class FailingErpAdapter:
    name = "failing"

    def lookup(self, code: str) -> ErpItem | None:
        raise ErpAdapterError("ERP unavailable")


def test_erp_reconcile_reports_adapter_errors(
    client: TestClient,
    admin_headers: dict[str, str],
    editor_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rule = make_rule(client, editor_headers)
    generated = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"family": "ELE"}},
        headers=editor_headers,
    )
    assert generated.status_code == 200
    code = generated.json()["code"]

    monkeypatch.setattr(integrations, "get_erp_adapter", lambda: FailingErpAdapter())
    response = client.post(
        "/api/integrations/erp/reconcile",
        json={"codes": [code]},
        headers=erp_key(client, admin_headers),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["errors"] == 1
    assert body["results"][0]["action"] == "error"
    assert "ERP unavailable" in body["results"][0]["error"]
