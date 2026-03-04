"""E2E test fixtures for Claude Code hook integration.

Provides:
- Frozen fixture loading from JSON files
- Real server subprocess management (start, health-check, teardown)
- Skip markers for optional Layer 3 tests
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Python interpreter from the same venv that's running the tests
PYTHON = sys.executable


def _free_port() -> int:
    """Find a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(base_url: str, timeout: float = 10.0) -> bool:
    """Poll /health until it returns 200 or timeout is reached."""
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2)
            if r.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.ReadError, OSError):
            pass
        time.sleep(0.2)
    return False


# --- Fixture loading ---


@pytest.fixture()
def load_fixture():
    """Return a helper that loads a JSON fixture by name."""
    def _load(name: str) -> dict:
        path = FIXTURES_DIR / name
        return json.loads(path.read_text())
    return _load


# --- Real server subprocess ---


@pytest.fixture()
def aiperture_server(tmp_path):
    """Start a real `aiperture serve` subprocess with isolated DB and log file.

    Yields a dict with: process, base_url, db_path, log_path, port.
    Kills the server on teardown.
    """
    import httpx  # noqa: F811

    port = _free_port()
    db_path = tmp_path / "e2e_test.db"
    log_path = tmp_path / "e2e_test.log"

    env = {
        **os.environ,
        "AIPERTURE_DB_PATH": str(db_path),
        "AIPERTURE_API_PORT": str(port),
        "AIPERTURE_API_HOST": "127.0.0.1",
        "AIPERTURE_LOG_FILE": str(log_path),
        "AIPERTURE_LOG_LEVEL": "DEBUG",
        # Lower learning thresholds for faster e2e tests
        "AIPERTURE_PERMISSION_LEARNING_MIN_DECISIONS": "3",
        "AIPERTURE_AUTO_APPROVE_THRESHOLD": "0.8",
        # No API key for tests
        "AIPERTURE_API_KEY": "",
    }

    # Initialize the DB first
    subprocess.run(
        [PYTHON, "-m", "aiperture.cli", "init-db"],
        env=env,
        check=True,
        capture_output=True,
    )

    # Start the server
    proc = subprocess.Popen(
        [PYTHON, "-m", "aiperture.cli", "serve"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base_url = f"http://127.0.0.1:{port}"

    if not _wait_for_health(base_url):
        # Server didn't start — capture output for debugging
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        pytest.fail(
            f"AIperture server failed to start on port {port}.\n"
            f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
        )

    yield {
        "process": proc,
        "base_url": base_url,
        "db_path": db_path,
        "log_path": log_path,
        "port": port,
    }

    # Teardown: graceful SIGTERM then force kill
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
