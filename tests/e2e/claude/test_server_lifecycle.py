"""Layer 2: Server lifecycle tests — real subprocess, real HTTP, real DB.

These tests start `aiperture serve` as a subprocess, POST Claude Code hook
payloads via HTTP, and verify end-to-end behavior including:
- Server startup and health check
- Hook endpoints returning correct decisions
- Full learning loop (N approvals -> auto-approve)
- High-risk guard preventing auto-approval
- Log file being written (catches the logging bug)
- Auto-allowed tools being skipped
"""

from __future__ import annotations

import time

import httpx
import pytest


class TestServerStartup:

    def test_server_starts_and_health(self, aiperture_server):
        """Server subprocess starts and /health returns healthy."""
        base_url = aiperture_server["base_url"]
        resp = httpx.get(f"{base_url}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestPermissionRequestHook:

    def test_unknown_pattern_returns_empty(self, aiperture_server):
        """PermissionRequest for unknown pattern returns {} (passthrough)."""
        base_url = aiperture_server["base_url"]
        resp = httpx.post(f"{base_url}/hooks/permission-request", json={
            "session_id": "e2e-test-unknown",
            "tool_name": "Bash",
            "tool_input": {"command": "some-unique-unknown-command-xyz"},
        }, timeout=5)
        assert resp.status_code == 200
        assert resp.json() == {}


class TestLearningLoop:

    def test_full_learning_loop_via_hooks(self, aiperture_server):
        """POST N PermissionRequest+PostToolUse pairs, then verify auto-approve.

        With min_decisions=3 and threshold=0.8 (set in conftest), approvals
        should eventually trigger auto-approve. Note: record_hook_decision
        records both original and normalized scope, so the decision count
        grows faster than 1-per-cycle. Once learning kicks in, PostToolUse
        returns reason=auto_approved instead of recorded=True.
        """
        base_url = aiperture_server["base_url"]
        tool_input = {"command": "npm test", "description": "Run tests"}
        auto_approved_seen = False

        # Seed approval cycles
        for i in range(3):
            session_id = f"e2e-learn-{i}"
            # PermissionRequest — creates pending entry (or auto-approves once learned)
            resp = httpx.post(f"{base_url}/hooks/permission-request", json={
                "session_id": session_id,
                "tool_name": "Bash",
                "tool_input": tool_input,
            }, timeout=5)
            assert resp.status_code == 200
            pr_data = resp.json()

            # PostToolUse — records implicit approval or detects auto-approval
            resp = httpx.post(f"{base_url}/hooks/post-tool-use", json={
                "session_id": session_id,
                "tool_name": "Bash",
                "tool_input": tool_input,
                "tool_use_id": f"toolu_learn_{i}",
                "tool_response": "All tests passed",
            }, timeout=5)
            assert resp.status_code == 200
            ptu_data = resp.json()

            if ptu_data.get("reason") == "auto_approved":
                # Learning kicked in — PermissionRequest auto-approved this cycle
                auto_approved_seen = True
                assert pr_data.get("hookSpecificOutput", {}).get("decision", {}).get("behavior") == "allow"
            else:
                assert ptu_data["recorded"] is True, (
                    f"Iteration {i}: PostToolUse unexpected: {ptu_data}"
                )

        # Small delay for background task processing
        time.sleep(0.5)

        # Final request should auto-approve
        resp = httpx.post(f"{base_url}/hooks/permission-request", json={
            "session_id": "e2e-learn-verify",
            "tool_name": "Bash",
            "tool_input": tool_input,
        }, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        hook_output = data.get("hookSpecificOutput", {})
        assert hook_output.get("decision", {}).get("behavior") == "allow", (
            f"Expected auto-approve after seeding, got: {data}"
        )


class TestHighRiskGuard:

    def test_high_risk_never_auto_approved(self, aiperture_server):
        """HIGH risk actions never auto-approve, even with learned patterns."""
        base_url = aiperture_server["base_url"]
        rm_input = {"command": "rm -rf /tmp/e2e-test-data"}

        # Seed approvals for dangerous command
        for i in range(5):
            session_id = f"e2e-risk-{i}"
            httpx.post(f"{base_url}/hooks/permission-request", json={
                "session_id": session_id,
                "tool_name": "Bash",
                "tool_input": rm_input,
            }, timeout=5)
            httpx.post(f"{base_url}/hooks/post-tool-use", json={
                "session_id": session_id,
                "tool_name": "Bash",
                "tool_input": rm_input,
                "tool_use_id": f"toolu_risk_{i}",
                "tool_response": "",
            }, timeout=5)

        time.sleep(0.5)

        # Should NOT auto-approve
        resp = httpx.post(f"{base_url}/hooks/permission-request", json={
            "session_id": "e2e-risk-verify",
            "tool_name": "Bash",
            "tool_input": rm_input,
        }, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        decision = data.get("hookSpecificOutput", {}).get("decision", {})
        assert decision.get("behavior") != "allow", (
            f"HIGH risk 'rm -rf' should never auto-approve, got: {data}"
        )


class TestLogFileWritten:

    def test_log_file_gets_written(self, aiperture_server):
        """Hook activity is written to the log file (catches the CLI logging bug)."""
        base_url = aiperture_server["base_url"]
        log_path = aiperture_server["log_path"]

        # POST a hook to generate log output
        httpx.post(f"{base_url}/hooks/permission-request", json={
            "session_id": "e2e-log-test",
            "tool_name": "Bash",
            "tool_input": {"command": "echo log-test"},
        }, timeout=5)

        # Small delay for file I/O
        time.sleep(0.5)

        assert log_path.exists(), f"Log file was not created at {log_path}"
        content = log_path.read_text()
        assert len(content) > 0, "Log file is empty"
        assert "aiperture" in content, "Log file missing aiperture log entries"


class TestAutoAllowedToolsSkipped:

    def test_auto_allowed_tools_not_recorded(self, aiperture_server):
        """Auto-allowed tools (Read, Grep, etc.) skip recording."""
        base_url = aiperture_server["base_url"]

        # Read is auto-allowed by default
        resp = httpx.post(f"{base_url}/hooks/post-tool-use", json={
            "session_id": "e2e-auto-allowed",
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.py"},
            "tool_use_id": "toolu_auto_allowed",
            "tool_response": "file contents",
        }, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert data["recorded"] is False
        assert data["reason"] == "hook_auto_allowed"

    def test_auto_allowed_permission_request_returns_empty(self, aiperture_server):
        """PermissionRequest for auto-allowed tools returns {} immediately."""
        base_url = aiperture_server["base_url"]

        resp = httpx.post(f"{base_url}/hooks/permission-request", json={
            "session_id": "e2e-auto-allowed-pr",
            "tool_name": "Grep",
            "tool_input": {"pattern": "TODO", "path": "src/"},
        }, timeout=5)
        assert resp.status_code == 200
        assert resp.json() == {}
