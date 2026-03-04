"""Tests for HTTP API authentication (Bearer token).

Verifies:
1. Requests pass when no API key is configured (local dev mode).
2. Requests pass with the correct Bearer token when an API key is set.
3. Requests fail with 401 when an API key is set but the token is wrong or missing.
"""

import aiperture.config
from fastapi.testclient import TestClient

from aiperture.api import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(api_key: str = "") -> TestClient:
    """Create a test client with the given API key configured."""
    aiperture.config.settings.api_key = api_key
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# No API key configured (open access / local dev mode)
# ---------------------------------------------------------------------------

class TestNoApiKey:
    """When AIPERTURE_API_KEY is empty, all requests should be allowed."""

    def test_health_no_key(self):
        client = _make_client(api_key="")
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "healthy")

    def test_permission_check_no_key(self):
        client = _make_client(api_key="")
        resp = client.post("/permissions/check", json={
            "tool": "filesystem",
            "action": "read",
            "scope": "README.md",
            "permissions": [],
        })
        assert resp.status_code == 200

    def test_config_get_no_key(self):
        client = _make_client(api_key="")
        resp = client.get("/config")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# API key configured + correct Bearer token
# ---------------------------------------------------------------------------

class TestCorrectApiKey:
    """When the correct Bearer token is provided, requests should succeed."""

    def test_health_with_correct_key(self):
        client = _make_client(api_key="test-secret-key-123")
        resp = client.get(
            "/health",
            headers={"Authorization": "Bearer test-secret-key-123"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "healthy")

    def test_permission_check_with_correct_key(self):
        client = _make_client(api_key="my-key")
        resp = client.post(
            "/permissions/check",
            json={
                "tool": "filesystem",
                "action": "read",
                "scope": "src/main.py",
                "permissions": [],
            },
            headers={"Authorization": "Bearer my-key"},
        )
        assert resp.status_code == 200

    def test_config_get_with_correct_key(self):
        client = _make_client(api_key="cfg-key")
        resp = client.get(
            "/config",
            headers={"Authorization": "Bearer cfg-key"},
        )
        assert resp.status_code == 200

    def test_audit_events_with_correct_key(self):
        client = _make_client(api_key="audit-key")
        resp = client.get(
            "/audit/events",
            headers={"Authorization": "Bearer audit-key"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# API key configured + wrong or missing token -> 401
# ---------------------------------------------------------------------------

class TestWrongOrMissingApiKey:
    """When the API key is set but the request has a wrong or missing token, return 401."""

    def test_missing_header_returns_401(self):
        client = _make_client(api_key="secret")
        resp = client.get("/health")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or missing API key"

    def test_wrong_key_returns_401(self):
        client = _make_client(api_key="correct-key")
        resp = client.get(
            "/health",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or missing API key"

    def test_empty_bearer_returns_401(self):
        client = _make_client(api_key="secret")
        resp = client.get(
            "/health",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    def test_non_bearer_scheme_returns_401(self):
        client = _make_client(api_key="secret")
        resp = client.get(
            "/health",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401

    def test_post_endpoint_without_key_returns_401(self):
        client = _make_client(api_key="secret")
        resp = client.post("/permissions/check", json={
            "tool": "filesystem",
            "action": "read",
            "scope": "test",
            "permissions": [],
        })
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or missing API key"

    def test_patch_config_without_key_returns_401(self):
        client = _make_client(api_key="secret")
        resp = client.patch("/config", json={"settings": {}})
        assert resp.status_code == 401

    def test_artifacts_store_without_key_returns_401(self):
        client = _make_client(api_key="secret")
        resp = client.post("/artifacts/store", json={"content": "test"})
        assert resp.status_code == 401
