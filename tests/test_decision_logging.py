"""Tests for permission decision logging and AIPERTURE_LOG_LEVEL setting."""

import logging

from aiperture.models import Permission, PermissionDecision
from aiperture.permissions import PermissionEngine


class TestDecisionLogging:
    """Verify _log_decision logs at correct levels."""

    def test_deny_logs_at_warning(self, caplog):
        engine = PermissionEngine()
        with caplog.at_level(logging.DEBUG, logger="aiperture.permissions.engine"):
            engine._log_decision(
                PermissionDecision.DENY, "filesystem", "read", "secret.txt", "static_rule",
            )
        assert any(
            r.levelno == logging.WARNING and "DENY" in r.message and "filesystem/read" in r.message
            for r in caplog.records
        )

    def test_ask_logs_at_info(self, caplog):
        engine = PermissionEngine()
        with caplog.at_level(logging.DEBUG, logger="aiperture.permissions.engine"):
            engine._log_decision(
                PermissionDecision.ASK, "shell", "execute", "git status", "auto_learned",
            )
        assert any(
            r.levelno == logging.INFO and "ASK" in r.message and "shell/execute" in r.message
            for r in caplog.records
        )

    def test_allow_logs_at_debug(self, caplog):
        engine = PermissionEngine()
        with caplog.at_level(logging.DEBUG, logger="aiperture.permissions.engine"):
            engine._log_decision(
                PermissionDecision.ALLOW, "filesystem", "read", "README.md", "auto_learned",
            )
        assert any(
            r.levelno == logging.DEBUG and "ALLOW" in r.message and "filesystem/read" in r.message
            for r in caplog.records
        )

    def test_deny_includes_scope_and_decided_by(self, caplog):
        engine = PermissionEngine()
        with caplog.at_level(logging.DEBUG, logger="aiperture.permissions.engine"):
            engine._log_decision(
                PermissionDecision.DENY, "shell", "execute", "rm -rf /", "static_rule",
            )
        record = [r for r in caplog.records if "DENY" in r.message][0]
        assert "rm -rf /" in record.message
        assert "static_rule" in record.message


class TestDecisionLoggingIntegration:
    """Verify that check() produces log output."""

    def test_static_deny_logs_warning(self, caplog):
        engine = PermissionEngine()
        rules = [Permission(tool="shell", action="execute", scope="ls", decision=PermissionDecision.ALLOW)]
        with caplog.at_level(logging.WARNING, logger="aiperture.permissions.engine"):
            engine.check("shell", "execute", "rm -rf /", rules)
        assert any(
            r.levelno == logging.WARNING and "DENY" in r.message
            for r in caplog.records
        )

    def test_static_allow_logs_debug(self, caplog):
        engine = PermissionEngine()
        rules = [Permission(tool="filesystem", action="read", scope="*", decision=PermissionDecision.ALLOW)]
        with caplog.at_level(logging.DEBUG, logger="aiperture.permissions.engine"):
            engine.check("filesystem", "read", "src/main.py", rules)
        assert any(
            r.levelno == logging.DEBUG and "ALLOW" in r.message
            for r in caplog.records
        )


class TestLogLevelConfig:
    """Verify the log_level setting in config."""

    def test_default_log_level_is_debug(self):
        from aiperture.config import Settings
        s = Settings()
        assert s.log_level.upper() == "DEBUG"

    def test_log_level_in_tunable_fields(self):
        from aiperture.config import Settings
        assert "log_level" in Settings.TUNABLE_FIELDS

    def test_log_level_has_description(self):
        from aiperture.config import Settings
        assert "log_level" in Settings.TUNABLE_DESCRIPTIONS

    def test_update_log_level_validates(self):
        import pytest
        from aiperture.config import update_settings
        with pytest.raises(ValueError, match="log_level"):
            update_settings({"log_level": "INVALID"})

    def test_update_log_level_accepts_valid(self):
        from aiperture.config import update_settings
        import aiperture.config
        original = aiperture.config.settings.log_level
        update_settings({"log_level": "warning"})
        assert aiperture.config.settings.log_level == "WARNING"
        # Reset
        update_settings({"log_level": original})
