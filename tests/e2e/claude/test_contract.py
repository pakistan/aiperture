"""Layer 1: Contract tests — validate hook endpoints against frozen Claude Code payloads.

These tests use FastAPI TestClient (no real server needed) and verify that:
- All frozen fixture payloads are accepted without errors
- Response schemas match what Claude Code expects
- Auto-allowed tools are correctly skipped
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from aiperture.api import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _client() -> TestClient:
    return TestClient(create_app())


class TestPermissionRequestContract:
    """Validate PermissionRequest hook response schema."""

    def test_bash_fixture_accepted(self):
        """Frozen Bash PermissionRequest payload returns valid response."""
        client = _client()
        payload = _load("permission_request_bash.json")
        resp = client.post("/hooks/permission-request", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        # Either {} (passthrough) or hookSpecificOutput with correct shape
        if data:
            hook_output = data["hookSpecificOutput"]
            assert hook_output["hookEventName"] == "PermissionRequest"
            assert hook_output["decision"]["behavior"] in ("allow", "deny")

    def test_edit_fixture_accepted(self):
        """Frozen Edit PermissionRequest payload returns valid response."""
        client = _client()
        payload = _load("permission_request_edit.json")
        resp = client.post("/hooks/permission-request", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        if data:
            hook_output = data["hookSpecificOutput"]
            assert hook_output["hookEventName"] == "PermissionRequest"
            assert hook_output["decision"]["behavior"] in ("allow", "deny")

    def test_write_fixture_accepted(self):
        """Frozen Write PermissionRequest payload returns valid response."""
        client = _client()
        payload = _load("permission_request_write.json")
        resp = client.post("/hooks/permission-request", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        if data:
            hook_output = data["hookSpecificOutput"]
            assert hook_output["hookEventName"] == "PermissionRequest"
            assert hook_output["decision"]["behavior"] in ("allow", "deny")

    def test_response_is_json(self):
        """Response Content-Type is application/json."""
        client = _client()
        payload = _load("permission_request_bash.json")
        resp = client.post("/hooks/permission-request", json=payload)
        assert "application/json" in resp.headers["content-type"]

    def test_unknown_pattern_returns_empty(self):
        """An unknown tool pattern returns {} (passthrough to Claude Code prompt)."""
        client = _client()
        payload = _load("permission_request_bash.json")
        # Use a unique session to avoid any cached state
        payload["session_id"] = "contract-unknown-pattern"
        resp = client.post("/hooks/permission-request", json=payload)
        assert resp.status_code == 200
        # No learned patterns exist in a fresh DB, so {} is expected
        assert resp.json() == {}


class TestPostToolUseContract:
    """Validate PostToolUse hook response schema."""

    def test_bash_fixture_accepted(self):
        """Frozen Bash PostToolUse payload returns valid response."""
        client = _client()
        payload = _load("post_tool_use_bash.json")
        resp = client.post("/hooks/post-tool-use", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "recorded" in data
        assert isinstance(data["recorded"], bool)

    def test_read_auto_allowed_skipped(self):
        """Read tool (default auto-allowed) returns hook_auto_allowed."""
        client = _client()
        payload = _load("post_tool_use_read.json")
        resp = client.post("/hooks/post-tool-use", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["recorded"] is False
        assert data["reason"] == "hook_auto_allowed"

    def test_response_is_json(self):
        """Response Content-Type is application/json."""
        client = _client()
        payload = _load("post_tool_use_bash.json")
        resp = client.post("/hooks/post-tool-use", json=payload)
        assert "application/json" in resp.headers["content-type"]

    def test_aiperture_mcp_tool_skipped(self):
        """AIperture's own MCP tools return recorded=False."""
        client = _client()
        resp = client.post("/hooks/post-tool-use", json={
            "session_id": "contract-test",
            "tool_name": "mcp__aiperture__check_permission",
            "tool_input": {"tool": "shell", "action": "execute", "scope": "ls"},
            "tool_use_id": "toolu_contract",
            "tool_response": "{}",
        })
        assert resp.status_code == 200
        assert resp.json()["recorded"] is False
