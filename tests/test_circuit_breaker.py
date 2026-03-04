"""Tests for database circuit breaker — permission checks fail closed (deny) on DB errors."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from aiperture.api import create_app
from aiperture.models.permission import Permission, PermissionDecision
from aiperture.permissions.engine import PermissionEngine


class TestEngineCircuitBreaker:
    """Permission engine fails closed when the database is unavailable."""

    def test_check_learned_returns_none_on_db_failure(self):
        """_check_learned returns None (no match) when the DB query throws."""
        engine = PermissionEngine()

        with patch("aiperture.permissions.engine.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("database is gone")
            result = engine._check_learned("filesystem", "read", "src/*.py", "default")

        assert result is None

    def test_check_task_permissions_returns_none_on_db_failure(self):
        """_check_task_permissions returns None (no match) when the DB query throws."""
        engine = PermissionEngine()

        with patch("aiperture.permissions.engine.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("connection refused")
            result = engine._check_task_permissions(
                "shell", "execute", "deploy.sh", "task-1", "default"
            )

        assert result is None

    def test_full_check_asks_on_db_failure_no_static_rules(self):
        """Full check() with no static rules returns ask (default) when DB is down."""
        engine = PermissionEngine()

        with patch("aiperture.permissions.engine.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("database unavailable")
            verdict = engine.check(
                "filesystem", "read", "src/main.py", [],
                task_id="task-1",
            )

        assert verdict.decision == "ask"

    def test_full_check_falls_through_to_static_on_db_failure(self):
        """When DB is down, check() still evaluates static rules after learned/ReBAC fail."""
        engine = PermissionEngine()
        rules = [
            Permission(tool="filesystem", action="read", scope="src/*", decision=PermissionDecision.ALLOW),
        ]

        with patch("aiperture.permissions.engine.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("database unavailable")
            verdict = engine.check(
                "filesystem", "read", "src/main.py", rules,
                task_id="task-1",
            )

        # Static rule matches, so it should allow despite DB failure
        assert verdict.decision == "allow"
        assert verdict.decided_by == "static_rule"

    def test_check_does_not_raise_on_db_failure(self):
        """check() never raises an unhandled exception due to DB failures."""
        engine = PermissionEngine()

        with patch("aiperture.permissions.engine.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("total db meltdown")
            # This must not raise
            verdict = engine.check(
                "shell", "execute", "ls", [],
                task_id="task-1",
            )

        assert verdict.decision == "ask"

    def test_db_failure_logs_warning_for_learned(self):
        """_check_learned logs a WARNING on database failure."""
        engine = PermissionEngine()

        with patch("aiperture.permissions.engine.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("db down")
            with patch("aiperture.permissions.engine.logger") as mock_logger:
                engine._check_learned("filesystem", "read", "src/*", "default")
                mock_logger.warning.assert_called_once()
                assert "failing closed" in mock_logger.warning.call_args[0][0].lower()

    def test_db_failure_logs_warning_for_task_permissions(self):
        """_check_task_permissions logs a WARNING on database failure."""
        engine = PermissionEngine()

        with patch("aiperture.permissions.engine.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("db down")
            with patch("aiperture.permissions.engine.logger") as mock_logger:
                engine._check_task_permissions(
                    "shell", "execute", "deploy.sh", "task-1", "default"
                )
                mock_logger.warning.assert_called_once()
                assert "failing closed" in mock_logger.warning.call_args[0][0].lower()


class TestHealthEndpoint:
    """Health endpoint reports database status."""

    def test_health_returns_healthy_when_db_works(self):
        """Health endpoint returns healthy status when database is connected."""
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["service"] == "aiperture"

    def test_health_returns_degraded_when_db_fails(self):
        """Health endpoint returns degraded status when database is unreachable."""
        app = create_app()
        client = TestClient(app)

        with patch("aiperture.api.routes.health.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("connection refused")
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["database"] == "error"
        assert "detail" in data
        assert "connection refused" in data["detail"]

    def test_health_degraded_includes_service_info(self):
        """Even in degraded mode, service name and version are returned."""
        app = create_app()
        client = TestClient(app)

        with patch("aiperture.api.routes.health.get_engine") as mock_get_engine:
            mock_get_engine.side_effect = Exception("timeout")
            resp = client.get("/health")

        data = resp.json()
        assert data["service"] == "aiperture"
        assert data["version"] == "0.2.0"
