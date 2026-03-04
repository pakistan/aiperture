"""Tests for cumulative session risk scoring."""

import aiperture.config
from aiperture.models.permission import Permission, PermissionDecision
from aiperture.permissions.engine import PermissionEngine


def _allow_all_rule():
    """Static rule that allows everything."""
    return [Permission(tool="*", action="*", scope="*", decision=PermissionDecision.ALLOW)]


class TestSessionRiskBudget:
    """Session risk budget should escalate to ASK when exhausted."""

    def test_budget_not_exhausted_allows(self):
        """Actions within budget should be allowed."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "session_risk_budget", 50.0)
        rules = _allow_all_rule()

        # LOW risk (0.1 each) — 10 checks = 1.0, well within budget
        for _ in range(10):
            verdict = engine.check(
                "filesystem", "read", "src/main.py", rules,
                session_id="sess1",
            )
            assert verdict.decision == PermissionDecision.ALLOW

    def test_budget_exhausted_escalates_to_ask(self):
        """Once budget is exhausted, ALLOW should escalate to ASK."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "session_risk_budget", 1.0)  # Very low budget
        rules = _allow_all_rule()

        results = []
        for _ in range(20):
            verdict = engine.check(
                "filesystem", "read", "src/main.py", rules,
                session_id="sess1",
            )
            results.append(verdict)

        # At some point, decisions should escalate to ASK
        ask_count = sum(1 for v in results if v.decision == PermissionDecision.ASK)
        assert ask_count > 0, "Expected some ASK verdicts after budget exhaustion"

    def test_different_sessions_independent(self):
        """Different sessions should have independent risk budgets."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "session_risk_budget", 1.0)
        rules = _allow_all_rule()

        # Exhaust session A's budget
        for _ in range(20):
            engine.check("filesystem", "read", "test.py", rules, session_id="A")

        # Session B should still have budget
        verdict = engine.check("filesystem", "read", "test.py", rules, session_id="B")
        assert verdict.decision == PermissionDecision.ALLOW

    def test_no_session_no_budget_tracking(self):
        """Checks without session_id should not be affected by risk budget."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "session_risk_budget", 0.5)
        rules = _allow_all_rule()

        for _ in range(100):
            verdict = engine.check("filesystem", "read", "test.py", rules)
            assert verdict.decision == PermissionDecision.ALLOW

    def test_disabled_with_zero_budget(self):
        """session_risk_budget=0 should disable risk budget tracking."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "session_risk_budget", 0.0)
        object.__setattr__(aiperture.config.settings, "rate_limit_per_minute", 0)  # disable rate limit
        rules = _allow_all_rule()

        for _ in range(500):
            verdict = engine.check(
                "filesystem", "read", "test.py", rules,
                session_id="sess1",
            )
            assert verdict.decision == PermissionDecision.ALLOW

    def test_get_remaining_budget(self):
        """get_session_risk_budget should return remaining budget."""
        engine = PermissionEngine()
        object.__setattr__(aiperture.config.settings, "session_risk_budget", 10.0)
        rules = _allow_all_rule()

        initial = engine.get_session_risk_budget("sess1")
        assert initial == 10.0

        # Make some checks (LOW risk = 0.1 each)
        for _ in range(5):
            engine.check("filesystem", "read", "test.py", rules, session_id="sess1")

        remaining = engine.get_session_risk_budget("sess1")
        assert remaining < initial
        assert remaining > 0
