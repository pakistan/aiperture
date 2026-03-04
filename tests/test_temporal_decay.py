"""Tests for temporal pattern decay — auto-learned patterns expire."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

import aiperture.config
from aiperture.db import get_engine
from aiperture.models.permission import PermissionDecision, PermissionLog
from aiperture.permissions.engine import PermissionEngine


def _seed_decisions(tool, action, scope, count, *, age_days=0, org_id="default"):
    """Insert permission log entries with a given age."""
    created = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=age_days)
    with Session(get_engine()) as session:
        for _ in range(count):
            session.add(PermissionLog(
                organization_id=org_id,
                tool=tool,
                action=action,
                scope=scope,
                decision=PermissionDecision.ALLOW,
                decided_by="human:tester",
                created_at=created,
            ))
        session.commit()


class TestTemporalDecay:
    """Auto-learned patterns should expire after pattern_max_age_days."""

    def setup_method(self):
        # Ensure consistent thresholds regardless of .aiperture.env values
        object.__setattr__(aiperture.config.settings, "permission_learning_min_decisions", 10)
        object.__setattr__(aiperture.config.settings, "auto_approve_threshold", 0.95)

    def test_recent_pattern_auto_approves(self):
        """Pattern with recent decisions should auto-approve normally."""
        engine = PermissionEngine()
        _seed_decisions("filesystem", "read", "src/*.py", 15, age_days=5)
        result = engine._check_learned("filesystem", "read", "src/main.py", "default")
        assert result == PermissionDecision.ALLOW

    def test_expired_pattern_returns_none(self):
        """Pattern where most recent decision is older than max_age returns None."""
        engine = PermissionEngine()
        _seed_decisions("filesystem", "read", "src/*.py", 15, age_days=100)
        result = engine._check_learned("filesystem", "read", "src/main.py", "default")
        assert result is None  # Falls through to ASK

    def test_custom_max_age_respected(self):
        """Custom pattern_max_age_days should be respected."""
        original = aiperture.config.settings.pattern_max_age_days
        try:
            object.__setattr__(aiperture.config.settings, "pattern_max_age_days", 30)
            engine = PermissionEngine()
            _seed_decisions("filesystem", "read", "docs/*.md", 15, age_days=35)
            result = engine._check_learned("filesystem", "read", "docs/guide.md", "default")
            assert result is None  # 35 days > 30 day max
        finally:
            object.__setattr__(aiperture.config.settings, "pattern_max_age_days", original)

    def test_pattern_at_boundary_still_approves(self):
        """Pattern exactly at max_age should still work (not expired yet)."""
        engine = PermissionEngine()
        _seed_decisions("filesystem", "read", "lib/*.py", 15, age_days=89)
        result = engine._check_learned("filesystem", "read", "lib/utils.py", "default")
        assert result == PermissionDecision.ALLOW

    def test_mix_old_and_recent_uses_most_recent(self):
        """If there are old AND recent decisions, most recent wins."""
        engine = PermissionEngine()
        _seed_decisions("filesystem", "read", "api/*.py", 10, age_days=100)  # old
        _seed_decisions("filesystem", "read", "api/*.py", 5, age_days=5)  # recent
        result = engine._check_learned("filesystem", "read", "api/routes.py", "default")
        assert result == PermissionDecision.ALLOW
