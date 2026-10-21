from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models import Item, Rule, User
from app.schemas import GenerateRequest, RuleUpdate
from app.services import generator
from app.services import rules as rule_service
from fastapi.testclient import TestClient
from sqlalchemy import select

from .conftest import login


def unique_key(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def make_rule(
    client: TestClient,
    headers: dict[str, str],
    *,
    key: str | None = None,
    definition: dict | None = None,
    document_type: str = "part",
    status: str = "active",
) -> dict:
    key = key or unique_key()
    prefix = f"T{key.replace('-', '')[:10].upper()}"
    payload = {
        "name": f"Rule {key}",
        "description": "test rule",
        "document_type": document_type,
        "key": key,
        "status": status,
        "definition": definition
        or {
            "segments": [
                {"type": "literal", "value": prefix},
                {"type": "separator", "value": "-"},
                {
                    "type": "list",
                    "key": "family",
                    "label": "Family",
                    "options": [
                        {"value": "MEC", "label": "Mechanical"},
                        {"value": "ELE", "label": "Electrical"},
                    ],
                },
                {"type": "separator", "value": "-"},
                {
                    "type": "counter",
                    "key": "seq",
                    "padding": 4,
                    "start": 1,
                    "step": 1,
                    "scope": "per_value",
                    "scope_keys": ["family"],
                },
            ],
            "max_length": 32,
            "case": "upper",
        },
    }
    response = client.post("/api/rules", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_login(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    bad = client.post("/api/auth/login", json={"email": "admin@demo.local", "password": "wrong"})
    assert bad.status_code == 401

    headers = login(client, "admin@demo.local", "Admin123!")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["email"] == "admin@demo.local"


def test_role_based_access(client: TestClient, viewer_headers: dict[str, str]) -> None:
    payload = {
        "name": "Viewer attempt",
        "key": unique_key("viewer"),
        "definition": {"segments": [{"type": "literal", "value": "NOPE"}]},
    }
    response = client.post("/api/rules", json=payload, headers=viewer_headers)
    assert response.status_code == 403

    # Viewers can still read and generate.
    assert client.get("/api/rules", headers=viewer_headers).status_code == 200


def test_rule_lifecycle_and_versioning(client: TestClient, editor_headers: dict[str, str]) -> None:
    rule = make_rule(client, editor_headers)
    assert rule["version"] == 1
    assert rule["status"] == "active"

    update = {
        "name": rule["name"],
        "description": "updated",
        "document_type": "part",
        "status": "active",
        "definition": {
            "segments": [
                {"type": "literal", "value": "UPD"},
                {"type": "separator", "value": "-"},
                {"type": "counter", "key": "seq", "padding": 3, "scope": "rule"},
            ]
        },
    }
    response = client.put(f"/api/rules/{rule['id']}", json=update, headers=editor_headers)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["version"] == 2
    assert updated["status"] == "active"
    assert updated["definition"]["segments"][0]["value"] == "UPD"

    versions = client.get(f"/api/rules/{rule['id']}/versions", headers=editor_headers).json()
    assert len(versions) == 2
    statuses = {v["version"]: v["status"] for v in versions}
    assert statuses[1] == "archived"
    assert statuses[2] == "active"

    archived = client.post(f"/api/rules/{updated['id']}/archive", headers=editor_headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    generate = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {}},
        headers=editor_headers,
    )
    assert generate.status_code == 404


def test_timestamps_include_utc_offset(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/auth/me", headers=admin_headers)
    assert response.status_code == 200
    value = response.json()["created_at"].replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_draft_version_does_not_hide_active_version(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    update = {
        "name": rule["name"],
        "description": "work in progress",
        "document_type": "part",
        "status": "draft",
        "definition": {
            "segments": [
                {"type": "literal", "value": "DRAFT"},
                {"type": "separator", "value": "-"},
                {"type": "counter", "key": "seq", "padding": 3, "scope": "rule"},
            ]
        },
    }
    response = client.put(f"/api/rules/{rule['id']}", json=update, headers=editor_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["version"] == 2

    active_rules = client.get(
        "/api/rules",
        params={"status_filter": "active"},
        headers=editor_headers,
    ).json()
    matching = [item for item in active_rules if item["key"] == rule["key"]]
    assert len(matching) == 1
    assert matching[0]["version"] == 1

    generate = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"family": "MEC"}},
        headers=editor_headers,
    )
    assert generate.status_code == 200
    assert generate.json()["rule_version"] == 1


def test_preview_does_not_consume_counter(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    values = {"family": "MEC"}
    first = client.post(
        "/api/generate/preview",
        json={"rule_key": rule["key"], "values": values},
        headers=editor_headers,
    )
    second = client.post(
        "/api/generate/preview",
        json={"rule_key": rule["key"], "values": values},
        headers=editor_headers,
    )
    assert first.status_code == 200
    assert first.json()["code"] == second.json()["code"]

    committed = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": values},
        headers=editor_headers,
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["code"] == first.json()["code"]


def test_scoped_counters_and_validation(client: TestClient, editor_headers: dict[str, str]) -> None:
    rule = make_rule(client, editor_headers)
    key = rule["key"]

    def generate(family: str):
        return client.post(
            "/api/generate",
            json={"rule_key": key, "values": {"family": family}},
            headers=editor_headers,
        )

    mec = generate("MEC").json()["code"]
    ele = generate("ELE").json()["code"]
    mec2 = generate("MEC").json()["code"]
    assert mec.endswith("-0001")
    assert ele.endswith("-0001")
    assert mec2.endswith("-0002")

    invalid = generate("XYZ")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "INVALID_INPUT"
    assert "family" in invalid.json()["detail"]["fields"]

    missing = client.post(
        "/api/generate", json={"rule_key": key, "values": {}}, headers=editor_headers
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["fields"]["family"]


def test_text_and_checksum_segments(client: TestClient, editor_headers: dict[str, str]) -> None:
    definition = {
        "segments": [
            {"type": "literal", "value": "TX"},
            {"type": "separator", "value": "-"},
            {
                "type": "text",
                "key": "serial",
                "label": "Serial",
                "min_length": 3,
                "max_length": 3,
                "regex": "^[0-9]{3}$",
            },
            {"type": "separator", "value": "-"},
            {"type": "checksum", "algorithm": "mod97"},
        ]
    }
    rule = make_rule(client, editor_headers, definition=definition)

    bad = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"serial": "abc"}},
        headers=editor_headers,
    )
    assert bad.status_code == 422
    assert "serial" in bad.json()["detail"]["fields"]

    good = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"serial": "123"}},
        headers=editor_headers,
    )
    assert good.status_code == 200, good.text
    code = good.json()["code"]
    assert code.startswith("TX-123-")
    assert len(code) == len("TX-123-") + 2


def test_external_reference_is_idempotent(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    body = {
        "rule_key": rule["key"],
        "values": {"family": "MEC"},
        "external_ref": f"vault://{uuid.uuid4().hex}/Part.SLDPRT",
    }
    first = client.post("/api/generate", json=body, headers=editor_headers)
    assert first.status_code == 200
    second = client.post("/api/generate", json=body, headers=editor_headers)
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "DUPLICATE_EXTERNAL_REF"
    assert detail["fields"]["code"] == first.json()["code"]
    assert detail["fields"]["external_ref"] == body["external_ref"]
    assert body["external_ref"] in detail["message"]


def test_generation_can_link_reference_and_metadata(
    client: TestClient, editor_headers: dict[str, str], viewer_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    external_ref = f"vault://{uuid.uuid4().hex}/Bracket.SLDPRT"
    response = client.post(
        "/api/generate",
        json={
            "rule_key": rule["key"],
            "values": {"family": "MEC"},
            "external_ref": f"  {external_ref}  ",
            "notes": "  linked from the web  ",
            "metadata": {"material": "S355", "revision": "A"},
        },
        headers=editor_headers,
    )
    assert response.status_code == 200, response.text
    item_id = response.json()["item_id"]

    item = client.get(f"/api/items/{item_id}", headers=viewer_headers)
    assert item.status_code == 200
    body = item.json()
    assert body["external_ref"] == external_ref
    assert body["notes"] == "  linked from the web  "
    assert body["payload"]["material"] == "S355"
    assert body["payload"]["revision"] == "A"
    assert body["payload"]["family"] == "MEC"

    duplicate = client.post(
        "/api/generate",
        json={
            "rule_key": rule["key"],
            "values": {"family": "MEC"},
            "external_ref": external_ref,
        },
        headers=editor_headers,
    )
    assert duplicate.status_code == 409
    detail = duplicate.json()["detail"]
    assert detail["code"] == "DUPLICATE_EXTERNAL_REF"
    assert detail["fields"]["external_ref"] == external_ref
    assert external_ref in detail["message"]
    assert detail["fields"]["code"] == response.json()["code"]


def test_item_link_can_be_edited_after_generation(
    client: TestClient,
    editor_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    rule = make_rule(client, editor_headers)

    def generate() -> str:
        response = client.post(
            "/api/generate",
            json={"rule_key": rule["key"], "values": {"family": "MEC"}},
            headers=editor_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()["item_id"]

    item_id = generate()
    external_ref = f"pdm:{uuid.uuid4().hex}"

    linked = client.patch(
        f"/api/items/{item_id}",
        json={
            "external_ref": external_ref,
            "notes": "  linked later  ",
            "metadata": {"material": "S355", "description": "Bracket"},
        },
        headers=editor_headers,
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["external_ref"] == external_ref
    assert body["notes"] == "linked later"
    assert body["payload"] == {"material": "S355", "description": "Bracket"}

    search = client.get("/api/items", params={"q": external_ref}, headers=viewer_headers)
    assert search.status_code == 200
    assert {item["id"] for item in search.json()["items"]} == {item_id}

    same = client.patch(
        f"/api/items/{item_id}",
        json={"external_ref": external_ref, "notes": "updated"},
        headers=editor_headers,
    )
    assert same.status_code == 200
    assert same.json()["external_ref"] == external_ref

    forbidden = client.patch(
        f"/api/items/{item_id}",
        json={"external_ref": f"pdm:{uuid.uuid4().hex}"},
        headers=viewer_headers,
    )
    assert forbidden.status_code == 403

    other_id = generate()
    conflict = client.patch(
        f"/api/items/{other_id}",
        json={"external_ref": external_ref},
        headers=editor_headers,
    )
    assert conflict.status_code == 409
    conflict_detail = conflict.json()["detail"]
    assert conflict_detail["code"] == "DUPLICATE_EXTERNAL_REF"
    assert conflict_detail["fields"]["external_ref"] == external_ref
    assert conflict_detail["fields"]["item_id"] == item_id

    voided = client.post(f"/api/items/{item_id}/void", headers=editor_headers)
    assert voided.status_code == 200

    reused = client.patch(
        f"/api/items/{other_id}",
        json={"external_ref": external_ref},
        headers=editor_headers,
    )
    assert reused.status_code == 200, reused.text
    assert reused.json()["external_ref"] == external_ref

    void_edit = client.patch(
        f"/api/items/{item_id}",
        json={"notes": "cannot edit a void item"},
        headers=editor_headers,
    )
    assert void_edit.status_code == 409

    audit = client.get(
        "/api/admin/audit",
        params={"action": "item.updated"},
        headers=editor_headers,
    )
    assert audit.status_code == 200
    assert audit.json()["total"] >= 2


def test_pdm_api_key_flow(
    client: TestClient, admin_headers: dict[str, str], editor_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    created = client.post(
        "/api/admin/api-keys", json={"name": "PDM connector"}, headers=admin_headers
    )
    assert created.status_code == 201, created.text
    secret = created.json()["key"]
    assert secret.startswith("pk_live_")

    headers = {"X-API-Key": secret}
    rules = client.get("/api/integrations/pdm/rules", headers=headers)
    assert rules.status_code == 200
    assert any(item["key"] == rule["key"] for item in rules.json())

    preview = client.post(
        "/api/integrations/pdm/preview",
        json={"rule_key": rule["key"], "values": {"family": "ELE"}},
        headers=headers,
    )
    assert preview.status_code == 200

    reserved = client.post(
        "/api/integrations/pdm/reserve",
        json={
            "rule_key": rule["key"],
            "values": {"family": "ELE"},
            "external_ref": f"pdm:{uuid.uuid4().hex}",
        },
        headers=headers,
    )
    assert reserved.status_code == 200, reserved.text
    code = reserved.json()["code"]

    lookup = client.get("/api/integrations/pdm/lookup", params={"code": code}, headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["exists"] is True
    assert lookup.json()["item"]["source"] == "pdm"

    missing = client.get(
        "/api/integrations/pdm/lookup",
        params={"code": "DOES-NOT-EXIST"},
        headers=headers,
    )
    assert missing.status_code == 200
    assert missing.json()["exists"] is False

    invalid = client.get("/api/integrations/pdm/rules", headers={"X-API-Key": "pk_live_bogus"})
    assert invalid.status_code == 401


def test_items_lookup_and_void(
    client: TestClient,
    editor_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    rule = make_rule(client, editor_headers)
    generated = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"family": "MEC"}},
        headers=editor_headers,
    ).json()
    code = generated["code"]

    lookup = client.get("/api/items/lookup", params={"code": code}, headers=viewer_headers)
    assert lookup.status_code == 200
    assert lookup.json()["code"] == code

    forbidden = client.post(f"/api/items/{generated['item_id']}/void", headers=viewer_headers)
    assert forbidden.status_code == 403

    voided = client.post(f"/api/items/{generated['item_id']}/void", headers=editor_headers)
    assert voided.status_code == 200
    assert voided.json()["status"] == "void"
    assert voided.json()["voided_at"] is not None

    again = client.post(f"/api/items/{generated['item_id']}/void", headers=editor_headers)
    assert again.status_code == 409


def test_audit_and_stats(
    client: TestClient, admin_headers: dict[str, str], editor_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"family": "MEC"}},
        headers=editor_headers,
    )

    audit = client.get(
        "/api/admin/audit", params={"action": "code.generated"}, headers=admin_headers
    )
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1
    assert audit.json()["items"][0]["action"] == "code.generated"

    stats = client.get("/api/admin/stats", headers=admin_headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["items_total"] >= 1
    assert body["active_rules"] >= 1
    assert "recent_items" in body
    assert body["by_source"].get("web", 0) >= 1

    assert client.get("/api/admin/stats", headers=editor_headers).status_code == 200

    forbidden = client.get("/api/admin/users", headers=editor_headers)
    assert forbidden.status_code == 403


def test_concurrent_generation_is_unique(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    key = rule["key"]

    def worker() -> str:
        with SessionLocal() as db:
            current = db.scalar(
                select(Rule).where(Rule.tenant_id == rule["tenant_id"], Rule.key == key)
            )
            assert current is not None
            request = GenerateRequest(rule_key=key, values={"family": "MEC"})
            item, _segments = generator.commit_code(
                db,
                tenant_id=rule["tenant_id"],
                rule=current,
                request=request,
                created_by=None,
            )
            return item.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: worker(), range(8)))

    assert len(codes) == 8
    assert len(set(codes)) == 8
    assert all(code.startswith("T") and "-MEC-" in code for code in codes)


def test_counter_collision_retries_with_next_value(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    token = uuid.uuid4().hex[:6].upper()
    literal = f"C{token}"
    definition = {
        "segments": [
            {"type": "literal", "value": literal},
            {"type": "separator", "value": "-"},
            {
                "type": "counter",
                "key": "seq",
                "padding": 3,
                "start": 1,
                "scope": "rule",
            },
        ],
        "max_length": 32,
        "case": "upper",
    }
    rule = make_rule(client, editor_headers, definition=definition)

    first = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {}},
        headers=editor_headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["code"] == f"{literal}-001"

    with SessionLocal() as db:
        rule_row = db.scalar(select(Rule).where(Rule.id == rule["id"]))
        assert rule_row is not None
        db.add(
            Item(
                tenant_id=rule["tenant_id"],
                code=f"{literal}-002",
                rule_id=rule_row.id,
                rule_key=rule["key"],
                rule_version=rule["version"],
                status="reserved",
                source="test",
                payload={},
            )
        )
        db.commit()

    retried = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {}},
        headers=editor_headers,
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["code"] == f"{literal}-003"


def test_generation_rejects_empty_code(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    definition = {
        "segments": [
            {
                "type": "list",
                "key": "family",
                "required": False,
                "options": [{"value": "MEC"}],
            }
        ]
    }
    rule = make_rule(client, editor_headers, definition=definition)

    preview = client.post(
        "/api/generate/preview",
        json={"rule_key": rule["key"], "values": {}},
        headers=editor_headers,
    )
    assert preview.status_code == 422
    assert preview.json()["detail"]["code"] == "EMPTY_CODE"

    committed = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {}},
        headers=editor_headers,
    )
    assert committed.status_code == 422
    assert committed.json()["detail"]["code"] == "EMPTY_CODE"


def test_rules_status_query_parameter(client: TestClient, editor_headers: dict[str, str]) -> None:
    active = make_rule(client, editor_headers)
    draft = make_rule(client, editor_headers, status="draft")

    response = client.get(
        "/api/rules",
        params={"status": "active"},
        headers=editor_headers,
    )
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()}
    assert active["key"] in keys
    assert draft["key"] not in keys

    alias = client.get(
        "/api/rules",
        params={"status_filter": "active"},
        headers=editor_headers,
    )
    assert alias.status_code == 200
    assert {item["key"] for item in alias.json()} == keys


def test_text_segment_accepts_min_max_aliases(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    definition = {
        "segments": [
            {"type": "literal", "value": "TX"},
            {"type": "separator", "value": "-"},
            {
                "type": "text",
                "key": "serial",
                "min": 3,
                "max": 5,
                "regex": "^[0-9]+$",
            },
        ]
    }
    rule = make_rule(client, editor_headers, definition=definition)

    text_segment = rule["definition"]["segments"][2]
    assert text_segment["min_length"] == 3
    assert text_segment["max_length"] == 5

    good = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"serial": "123"}},
        headers=editor_headers,
    )
    assert good.status_code == 200, good.text

    bad = client.post(
        "/api/generate",
        json={"rule_key": rule["key"], "values": {"serial": "12"}},
        headers=editor_headers,
    )
    assert bad.status_code == 422
    assert "serial" in bad.json()["detail"]["fields"]


def test_concurrent_rule_updates_create_distinct_versions(
    client: TestClient, editor_headers: dict[str, str]
) -> None:
    rule = make_rule(client, editor_headers)
    barrier = threading.Barrier(2)

    def worker(literal: str) -> int:
        with SessionLocal() as db:
            current = db.scalar(select(Rule).where(Rule.id == rule["id"]))
            author = db.scalar(select(User).where(User.id == rule["created_by"]))
            assert current is not None and author is not None
            payload = RuleUpdate(
                name=rule["name"],
                description=f"updated by {literal}",
                document_type="part",
                status="active",
                definition={
                    "segments": [
                        {"type": "literal", "value": literal},
                        {"type": "separator", "value": "-"},
                        {"type": "counter", "key": "seq", "padding": 3, "scope": "rule"},
                    ]
                },
            )
            barrier.wait()
            update = rule_service.update_rule(
                db,
                tenant_id=rule["tenant_id"],
                rule=current,
                payload=payload,
                author=author,
            )
            return update.version

    with ThreadPoolExecutor(max_workers=2) as pool:
        versions = list(pool.map(worker, ["UPA", "UPB"]))

    assert sorted(versions) == [2, 3]
    with SessionLocal() as db:
        rows = db.scalars(
            select(Rule).where(Rule.key == rule["key"]).order_by(Rule.version)
        ).all()
        assert [row.version for row in rows] == [1, 2, 3]
        assert [row.status for row in rows] == ["archived", "archived", "active"]
