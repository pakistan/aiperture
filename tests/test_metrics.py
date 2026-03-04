"""Tests for Prometheus metrics instrumentation."""

import prometheus_client

from aiperture.metrics import (
    AUTO_APPROVED,
    PERMISSION_CHECK_DURATION,
    PERMISSION_CHECKS,
    RATE_LIMITED,
    SESSION_CACHE_HITS,
    SESSION_CACHE_MISSES,
)
from aiperture.models.permission import Permission, PermissionDecision
from aiperture.permissions.engine import PermissionEngine


def _reset_metrics():
    """Reset all Prometheus counters for test isolation."""
    # CollectorRegistry doesn't support easy reset, so we use the internal _metrics
    # For tests, we just check that values increase
    pass


class TestMetricsInstrumentation:
    """Permission checks should increment Prometheus metrics."""

    def test_check_increments_counter(self):
        """Each permission check should increment the total counter."""
        engine = PermissionEngine()
        before = PERMISSION_CHECKS.labels(decision="ask", decided_by="default")._value.get()

        engine.check("filesystem", "read", "test.py", [])

        after = PERMISSION_CHECKS.labels(decision="ask", decided_by="default")._value.get()
        assert after > before

    def test_allow_decision_tracked(self):
        """ALLOW decisions should be tracked."""
        engine = PermissionEngine()
        rules = [Permission(tool="*", action="*", scope="*", decision=PermissionDecision.ALLOW)]
        before = PERMISSION_CHECKS.labels(decision="allow", decided_by="static_rule")._value.get()

        engine.check("filesystem", "read", "test.py", rules)

        after = PERMISSION_CHECKS.labels(decision="allow", decided_by="static_rule")._value.get()
        assert after > before

    def test_cache_hit_tracked(self):
        """Session cache hits should be tracked after human decision."""
        from aiperture.permissions.challenge import create_challenge

        engine = PermissionEngine()
        before_hits = SESSION_CACHE_HITS._value.get()

        # Record a human decision (this caches in session memory)
        ch = create_challenge("filesystem", "read", "test.py", organization_id="default", session_id="s1")
        engine.record_human_decision(
            "filesystem", "read", "test.py",
            PermissionDecision.ALLOW, "user1",
            challenge=ch.token, challenge_nonce=ch.nonce,
            challenge_issued_at=ch.issued_at,
            session_id="s1",
        )
        # Next check should hit session cache
        engine.check("filesystem", "read", "test.py", [], session_id="s1")

        after_hits = SESSION_CACHE_HITS._value.get()
        assert after_hits > before_hits

    def test_cache_miss_tracked(self):
        """Session cache misses should be tracked."""
        engine = PermissionEngine()
        before = SESSION_CACHE_MISSES._value.get()

        engine.check("filesystem", "read", "test.py", [], session_id="s2")

        after = SESSION_CACHE_MISSES._value.get()
        assert after > before

    def test_duration_recorded(self):
        """Check duration should be recorded in histogram."""
        engine = PermissionEngine()
        before = PERMISSION_CHECK_DURATION._sum.get()

        engine.check("filesystem", "read", "test.py", [])

        after = PERMISSION_CHECK_DURATION._sum.get()
        assert after > before

    def test_metrics_endpoint_format(self):
        """Metrics should be available in Prometheus text format."""
        output = prometheus_client.generate_latest().decode()
        assert "aiperture_permission_checks_total" in output
        assert "aiperture_permission_check_duration_seconds" in output
