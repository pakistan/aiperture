"""Tests for rate limiting — per-session permission check throttling."""

import aiperture.config
from aiperture.models.permission import Permission, PermissionDecision
from aiperture.permissions.engine import PermissionEngine


class TestRateLimiting:
    """Per-session rate limiting on permission checks."""

    def test_under_limit_allowed(self):
        """Checks under the rate limit should proceed normally."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "rate_limit_per_minute", 10)

        for _ in range(10):
            verdict = engine.check(
                "filesystem", "read", "src/main.py", [],
                session_id="sess1", organization_id="org1",
            )
            assert verdict.decided_by != "rate_limit"

    def test_over_limit_denied(self):
        """Checks over the rate limit should be denied."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "rate_limit_per_minute", 5)

        results = []
        for _ in range(8):
            verdict = engine.check(
                "filesystem", "read", "src/main.py", [],
                session_id="sess1", organization_id="org1",
            )
            results.append(verdict)

        # First 5 should proceed normally (denied by static rules, not rate limit)
        for v in results[:5]:
            assert v.decided_by != "rate_limit"

        # 6th+ should be rate limited
        for v in results[5:]:
            assert v.decision == PermissionDecision.DENY
            assert v.decided_by == "rate_limit"

    def test_different_sessions_independent(self):
        """Different sessions should have independent rate limits."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "rate_limit_per_minute", 3)

        # Session A: 3 checks (at limit)
        for _ in range(3):
            engine.check("filesystem", "read", "test.py", [], session_id="A")

        # Session B should still work
        verdict = engine.check("filesystem", "read", "test.py", [], session_id="B")
        assert verdict.decided_by != "rate_limit"

    def test_no_session_no_rate_limit(self):
        """Checks without session_id should not be rate limited."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "rate_limit_per_minute", 2)

        for _ in range(10):
            verdict = engine.check("filesystem", "read", "test.py", [])
            assert verdict.decided_by != "rate_limit"

    def test_zero_limit_means_unlimited(self):
        """rate_limit_per_minute=0 should disable rate limiting."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "rate_limit_per_minute", 0)

        for _ in range(500):
            verdict = engine.check(
                "filesystem", "read", "test.py", [],
                session_id="sess1",
            )
            assert verdict.decided_by != "rate_limit"
