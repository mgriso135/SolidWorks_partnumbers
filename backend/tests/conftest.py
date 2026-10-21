from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="partcode-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-production"
os.environ["SEED_DEMO"] = "true"
os.environ["ENVIRONMENT"] = "test"

from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client: TestClient) -> dict[str, str]:
    return login(client, "admin@demo.local", "Admin123!")


@pytest.fixture(scope="session")
def editor_headers(client: TestClient) -> dict[str, str]:
    return login(client, "editor@demo.local", "Editor123!")


@pytest.fixture(scope="session")
def viewer_headers(client: TestClient) -> dict[str, str]:
    return login(client, "viewer@demo.local", "Viewer123!")
