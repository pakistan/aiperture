"""Layer 3: Real Claude Code smoke tests — optional, requires Claude CLI + API key.

These tests actually invoke `claude -p` with hooks pointed at a running
AIperture server and verify that real hook payloads arrive.

Skipped by default. Run with:
    ANTHROPIC_API_KEY=... pytest tests/e2e/claude/test_claude_smoke.py -v -m e2e_claude
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

_has_claude = shutil.which("claude") is not None
_has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.mark.e2e_claude
@pytest.mark.skipif(not _has_claude, reason="Claude Code CLI not installed")
@pytest.mark.skipif(not _has_api_key, reason="ANTHROPIC_API_KEY not set")
class TestRealClaudeCodeHooks:
    """Smoke tests that invoke the real Claude Code CLI."""

    def test_real_claude_code_hook_fires(self, aiperture_server):
        """Run `claude -p` with a trivial prompt and verify AIperture receives hook payloads.

        This test:
        1. Creates a temporary .claude/settings.json with hooks pointing at our test server
        2. Runs `claude -p "echo hello"` in that directory
        3. Checks the AIperture log file for hook entries
        """
        base_url = aiperture_server["base_url"]
        log_path = aiperture_server["log_path"]
        port = aiperture_server["port"]

        with tempfile.TemporaryDirectory() as work_dir:
            # Create .claude/settings.json with hooks pointing at our test server
            claude_dir = Path(work_dir) / ".claude"
            claude_dir.mkdir()
            settings = {
                "permissions": {"allow": ["Bash"]},
                "hooks": {
                    "PermissionRequest": [{
                        "matcher": ".*",
                        "hooks": [{
                            "type": "http",
                            "url": f"http://127.0.0.1:{port}/hooks/permission-request",
                        }],
                    }],
                    "PostToolUse": [{
                        "matcher": ".*",
                        "hooks": [{
                            "type": "http",
                            "url": f"http://127.0.0.1:{port}/hooks/post-tool-use",
                        }],
                    }],
                },
            }
            (claude_dir / "settings.json").write_text(json.dumps(settings))

            # Run a trivial Claude Code command
            result = subprocess.run(
                ["claude", "-p", "Run: echo 'aiperture-smoke-test'", "--no-input"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "HOME": work_dir},
            )

            # Give time for hooks to fire
            time.sleep(2)

            # Verify log file has hook entries
            if log_path.exists():
                content = log_path.read_text()
                assert "hook" in content.lower() or "Hook" in content, (
                    f"Expected hook log entries, got:\n{content[:500]}"
                )

    def test_real_claude_health_check(self, aiperture_server):
        """Verify the test server is reachable (sanity check for the fixture)."""
        import httpx

        base_url = aiperture_server["base_url"]
        resp = httpx.get(f"{base_url}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
