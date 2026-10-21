#!/usr/bin/env python3
"""A disposable mock of the PDM side of the PartCode connector.

This is not a SolidWorks PDM API server. PDM exposes a local COM/.NET API, so
it cannot be recreated faithfully outside Windows. This service emulates the
part that matters for integration testing: a vault with files, data-card
variables, and the exact HTTP calls the real add-in makes to PartCode.
"""

from __future__ import annotations

import copy
import json
import os
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML = (BASE_DIR / "index.html").read_text(encoding="utf-8")

PARTCODE_URL = os.getenv("PARTCODE_URL", "http://host.docker.internal:7000").rstrip("/")
PARTCODE_API_KEY = os.getenv("PARTCODE_API_KEY", "").strip()
PDM_VAULT = os.getenv("PDM_VAULT", "SandboxVault")
TARGET_VARIABLE = os.getenv("TARGET_VARIABLE", "PartNumber")
DOCUMENT_TYPE = os.getenv("DOCUMENT_TYPE", "part")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7100"))
PARTCODE_TLS_INSECURE = os.getenv("PARTCODE_TLS_INSECURE", "").lower() in {
    "1",
    "true",
    "yes",
}

SOURCE_VARIABLES = {
    "Description": "description",
    "Material": "material",
    "Family": "family",
}

STATE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def seed_files() -> dict[int, dict[str, Any]]:
    return {
        1001: {
            "id": 1001,
            "vault": PDM_VAULT,
            "name": "BRACKET-01.sldprt",
            "path": f"\\\\{PDM_VAULT}\\Parts\\BRACKET-01.sldprt",
            "variables": {
                "Description": "Mounting bracket",
                "Material": "AISI 304",
                "Family": "MEC",
                TARGET_VARIABLE: "",
            },
            "assigned": None,
            "history": [],
        },
        1002: {
            "id": 1002,
            "vault": PDM_VAULT,
            "name": "SHAFT-02.sldprt",
            "path": f"\\\\{PDM_VAULT}\\Parts\\SHAFT-02.sldprt",
            "variables": {
                "Description": "Drive shaft",
                "Material": "42CrMo4",
                "Family": "MEC",
                TARGET_VARIABLE: "",
            },
            "assigned": None,
            "history": [],
        },
        1003: {
            "id": 1003,
            "vault": PDM_VAULT,
            "name": "SENSOR-BOX.sldasm",
            "path": f"\\\\{PDM_VAULT}\\Assemblies\\SENSOR-BOX.sldasm",
            "variables": {
                "Description": "Sensor control box",
                "Material": "Aluminium",
                "Family": "ELE",
                TARGET_VARIABLE: "",
            },
            "assigned": None,
            "history": [],
        },
    }


FILES = seed_files()


def public_file(file: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(file)


def file_or_404(file_id: int) -> dict[str, Any] | None:
    with STATE_LOCK:
        file = FILES.get(file_id)
        return copy.deepcopy(file) if file is not None else None


def external_ref(file: dict[str, Any]) -> str:
    return f"PDM:{file['vault']}:{file['id']}"


def partcode_call(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, Any]:
    if not PARTCODE_API_KEY:
        return 503, {
            "detail": (
                "PARTCODE_API_KEY is not set. Create a key in PartCode and restart the sandbox."
            )
        }

    headers = {
        "Accept": "application/json",
        "X-API-Key": PARTCODE_API_KEY,
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        PARTCODE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )

    context = None
    if PARTCODE_TLS_INSECURE and PARTCODE_URL.startswith("https://"):
        context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"detail": raw}
    except urllib.error.URLError as error:
        return 502, {"detail": f"PartCode is unreachable at {PARTCODE_URL}: {error.reason}"}
    except TimeoutError:
        return 504, {"detail": f"PartCode timed out at {PARTCODE_URL}"}


def build_request(
    file: dict[str, Any],
    rule_key: str,
    overrides: dict[str, Any],
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values: dict[str, str] = {}
    metadata: dict[str, Any] = {
        "pdm_path": file["path"],
        "pdm_file_id": str(file["id"]),
        "pdm_file_name": file["name"],
        "pdm_vault": file["vault"],
    }

    for pdm_name, partcode_name in SOURCE_VARIABLES.items():
        raw = overrides.get(pdm_name)
        if raw is None:
            raw = overrides.get(partcode_name)
        if raw is None:
            raw = file["variables"].get(pdm_name, "")

        text = str(raw).strip()
        if not text:
            continue

        values[pdm_name] = text
        values[partcode_name] = text
        metadata[partcode_name] = text

    for key, raw in overrides.items():
        if key in values:
            continue
        text = str(raw).strip()
        if text:
            values[key] = text

    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "rule_key": rule_key,
        "values": values,
        "source": "pdm",
        "external_ref": external_ref(file),
        "metadata": metadata,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "PartCodePdmSandbox/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def _send_json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self) -> None:
        data = INDEX_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON body: {error}") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _file_id(self, parts: list[str]) -> int | None:
        if len(parts) < 3 or parts[0] != "api" or parts[1] != "files":
            return None
        try:
            return int(parts[2])
        except ValueError:
            return None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        parts = [part for part in path.split("/") if part]

        if path in ("/", "/index.html"):
            self._send_html()
            return

        if path == "/health":
            with STATE_LOCK:
                file_count = len(FILES)
            self._send_json(
                200,
                {
                    "status": "ok",
                    "partcode_url": PARTCODE_URL,
                    "api_key_configured": bool(PARTCODE_API_KEY),
                    "vault": PDM_VAULT,
                    "document_type": DOCUMENT_TYPE,
                    "target_variable": TARGET_VARIABLE,
                    "files": file_count,
                },
            )
            return

        if path == "/api/files":
            with STATE_LOCK:
                files = [public_file(file) for file in FILES.values()]
            self._send_json(200, files)
            return

        if path == "/api/rules":
            query = urllib.parse.parse_qs(parsed.query)
            document_type = query.get("document_type", [DOCUMENT_TYPE])[0]
            status, payload = partcode_call(
                "GET",
                "/api/integrations/pdm/rules?document_type=" + urllib.parse.quote(document_type),
            )
            self._send_json(status, payload)
            return

        if path == "/api/lookup":
            query = urllib.parse.parse_qs(parsed.query)
            code = query.get("code", [""])[0].strip()
            if not code:
                self._send_json(400, {"detail": "The code query parameter is required."})
                return
            status, payload = partcode_call(
                "GET",
                "/api/integrations/pdm/lookup?code=" + urllib.parse.quote(code),
            )
            self._send_json(status, payload)
            return

        file_id = self._file_id(parts)
        if file_id is not None and len(parts) == 3:
            file = file_or_404(file_id)
            if file is None:
                self._send_json(404, {"detail": f"File {file_id} not found."})
                return
            self._send_json(200, file)
            return

        self._send_json(404, {"detail": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        parts = [part for part in path.split("/") if part]

        try:
            body = self._read_json()
        except ValueError as error:
            self._send_json(400, {"detail": str(error)})
            return

        if path == "/api/reset":
            with STATE_LOCK:
                FILES.clear()
                FILES.update(seed_files())
            self._send_json(200, {"status": "reset", "files": len(FILES)})
            return

        file_id = self._file_id(parts)
        if file_id is None:
            self._send_json(404, {"detail": "Not found."})
            return

        file = file_or_404(file_id)
        if file is None:
            self._send_json(404, {"detail": f"File {file_id} not found."})
            return

        if len(parts) == 4 and parts[3] == "reset":
            with STATE_LOCK:
                target = FILES[file_id]
                target["variables"][TARGET_VARIABLE] = ""
                target["assigned"] = None
                target["history"] = []
            self._send_json(200, file_or_404(file_id))
            return

        if len(parts) != 4 or parts[3] not in ("preview", "reserve"):
            self._send_json(404, {"detail": "Not found."})
            return

        rule_key = str(body.get("rule_key") or "").strip()
        if not rule_key:
            self._send_json(400, {"detail": "rule_key is required."})
            return

        overrides = body.get("values") or {}
        if not isinstance(overrides, dict):
            self._send_json(400, {"detail": "values must be an object."})
            return

        extra_metadata = body.get("metadata") or {}
        if not isinstance(extra_metadata, dict):
            self._send_json(400, {"detail": "metadata must be an object."})
            return

        request = build_request(file, rule_key, overrides, extra_metadata)

        if parts[3] == "preview":
            status, payload = partcode_call("POST", "/api/integrations/pdm/preview", request)
            self._send_json(status, payload)
            return

        status, payload = partcode_call("POST", "/api/integrations/pdm/reserve", request)
        if status >= 400:
            self._send_json(status, payload)
            return

        code = payload.get("code")
        if not code:
            self._send_json(502, {"detail": "PartCode returned no code.", "response": payload})
            return

        with STATE_LOCK:
            target = FILES.get(file_id)
            if target is None:
                self._send_json(404, {"detail": f"File {file_id} not found."})
                return
            target["variables"][TARGET_VARIABLE] = code
            target["assigned"] = {
                "code": code,
                "item_id": payload.get("item_id"),
                "rule_key": payload.get("rule_key"),
                "rule_version": payload.get("rule_version"),
                "external_ref": external_ref(file),
                "at": _now(),
            }
            target["history"].append(
                {
                    "action": "reserved",
                    "code": code,
                    "item_id": payload.get("item_id"),
                    "at": _now(),
                }
            )
            updated = public_file(target)

        self._send_json(200, {"result": payload, "file": updated})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"PartCode PDM sandbox listening on http://{HOST}:{PORT}", flush=True)
    print(f"PartCode URL: {PARTCODE_URL}", flush=True)
    print(
        f"Vault: {PDM_VAULT} | document type: {DOCUMENT_TYPE} | target: {TARGET_VARIABLE}",
        flush=True,
    )
    if not PARTCODE_API_KEY:
        print(
            "WARNING: PARTCODE_API_KEY is not set; rules and assignment calls will fail.",
            flush=True,
        )
    if PARTCODE_TLS_INSECURE:
        print("WARNING: TLS certificate verification is disabled for PartCode calls.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
