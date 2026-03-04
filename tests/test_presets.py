"""Tests for bootstrap presets."""

import pytest

from aiperture.permissions.presets import (
    PRESET_DEVELOPER,
    PRESET_MINIMAL,
    PRESET_READONLY,
    apply_preset,
    get_preset,
    get_preset_names,
)


class TestPresetDefinitions:
    def test_developer_preset_has_git_status(self):
        scopes = [p.scope for p in PRESET_DEVELOPER if p.tool == "shell"]
        assert any("git status" in s for s in scopes)

    def test_readonly_preset_has_filesystem_read(self):
        tools = [p.tool for p in PRESET_READONLY]
        assert "filesystem" in tools

    def test_minimal_preset_is_empty(self):
        assert len(PRESET_MINIMAL) == 0

    def test_developer_extends_readonly(self):
        assert len(PRESET_DEVELOPER) > len(PRESET_READONLY)

    def test_get_preset_names(self):
        names = get_preset_names()
        assert "developer" in names
        assert "readonly" in names
        assert "minimal" in names

    def test_get_preset_valid(self):
        preset = get_preset("developer")
        assert len(preset) > 0

    def test_get_preset_unknown_raises(self):
        with pytest.raises(KeyError):
            get_preset("nonexistent")


class TestApplyPreset:
    def test_apply_creates_decisions(self):
        total = apply_preset("developer")
        assert total > 0

    def test_apply_minimal_creates_nothing(self):
        total = apply_preset("minimal")
        assert total == 0

    def test_bootstrap_decisions_enable_auto_approve(self):
        """After applying preset, check_permission auto-approves matching patterns."""
        from aiperture.permissions.engine import PermissionEngine

        apply_preset("developer")
        engine = PermissionEngine()
        # git status should now auto-approve
        verdict = engine.check("shell", "execute", "git status", [])
        assert verdict.decision == "allow"
        assert verdict.decided_by == "auto_learned"

    def test_bootstrap_decided_by_tagged(self):
        """All bootstrap decisions have decided_by='human:bootstrap'."""
        from sqlmodel import Session, select

        from aiperture.db.engine import get_engine
        from aiperture.models.permission import PermissionLog

        apply_preset("readonly")
        with Session(get_engine()) as session:
            logs = session.exec(select(PermissionLog)).all()
            for log in logs:
                assert log.decided_by == "human:bootstrap"

    def test_custom_num_decisions(self):
        """Can override number of synthetic decisions per pattern."""
        total = apply_preset("readonly", num_synthetic_decisions=2)
        readonly_count = len(PRESET_READONLY)
        assert total == readonly_count * 2
