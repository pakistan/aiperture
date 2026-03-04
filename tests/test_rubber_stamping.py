"""Tests for rubber-stamping detection — rapid approvals flagged."""

import time
from unittest.mock import patch

from sqlmodel import Session

import aiperture.config
from aiperture.db import get_engine
from aiperture.models.permission import PermissionDecision, PermissionLog
from aiperture.permissions.challenge import create_challenge
from aiperture.permissions.engine import PermissionEngine


def _make_challenge(tool, action, scope, org_id="default", session_id="sess1"):
    return create_challenge(tool, action, scope, organization_id=org_id, session_id=session_id)


class TestRubberStampingDetection:
    """Rapid approvals should be flagged with :rapid suffix."""

    def test_normal_speed_not_flagged(self):
        """Approvals at normal speed should not be flagged."""
        engine = PermissionEngine()
        # Record 3 approvals (below min_count of 5)
        for _ in range(3):
            ch = _make_challenge("filesystem", "read", "src/main.py")
            log = engine.record_human_decision(
                "filesystem", "read", "src/main.py",
                PermissionDecision.ALLOW, "user1",
                challenge=ch.token, challenge_nonce=ch.nonce,
                challenge_issued_at=ch.issued_at,
                session_id="sess1",
            )
            assert not log.decided_by.endswith(":rapid")

    def test_rapid_approvals_flagged(self):
        """5+ approvals within 60s should be flagged as rapid."""
        engine = PermissionEngine()
        logs = []
        for _ in range(6):
            ch = _make_challenge("filesystem", "read", "src/utils.py", session_id="sess2")
            log = engine.record_human_decision(
                "filesystem", "read", "src/utils.py",
                PermissionDecision.ALLOW, "user1",
                challenge=ch.token, challenge_nonce=ch.nonce,
                challenge_issued_at=ch.issued_at,
                session_id="sess2",
            )
            logs.append(log)
        # First 4 should be normal, 5th+ should be rapid
        assert not logs[0].decided_by.endswith(":rapid")
        assert logs[4].decided_by.endswith(":rapid")
        assert logs[5].decided_by.endswith(":rapid")

    def test_denials_not_tracked(self):
        """Only approvals are tracked for rubber-stamping, not denials."""
        engine = PermissionEngine()
        for _ in range(6):
            ch = _make_challenge("filesystem", "write", "src/danger.py", session_id="sess3")
            log = engine.record_human_decision(
                "filesystem", "write", "src/danger.py",
                PermissionDecision.DENY, "user1",
                challenge=ch.token, challenge_nonce=ch.nonce,
                challenge_issued_at=ch.issued_at,
                session_id="sess3",
            )
            # Denials should never get :rapid suffix
            assert log.decided_by == "human:user1"

    def test_rapid_excluded_from_learning(self):
        """Rapid decisions should be excluded from _check_learned."""
        engine = PermissionEngine()
        # Seed 15 rapid decisions directly in DB
        with Session(get_engine()) as session:
            for _ in range(15):
                session.add(PermissionLog(
                    organization_id="default",
                    tool="filesystem", action="read", scope="test/*.py",
                    decision=PermissionDecision.ALLOW,
                    decided_by="human:user1:rapid",
                ))
            session.commit()

        # Should NOT auto-approve because all decisions are :rapid
        result = engine._check_learned("filesystem", "read", "test/foo.py", "default")
        assert result is None

    def test_custom_config(self):
        """Custom rapid approval config should be respected."""
        original_window = aiperture.config.settings.rapid_approval_window_seconds
        original_count = aiperture.config.settings.rapid_approval_min_count
        try:
            object.__setattr__(aiperture.config.settings, "rapid_approval_window_seconds", 10)
            object.__setattr__(aiperture.config.settings, "rapid_approval_min_count", 3)

            engine = PermissionEngine()
            logs = []
            for _ in range(4):
                ch = _make_challenge("shell", "execute", "ls -la", session_id="sess4")
                log = engine.record_human_decision(
                    "shell", "execute", "ls -la",
                    PermissionDecision.ALLOW, "user1",
                    challenge=ch.token, challenge_nonce=ch.nonce,
                    challenge_issued_at=ch.issued_at,
                    session_id="sess4",
                )
                logs.append(log)
            # With min_count=3, 3rd approval should be flagged
            assert logs[2].decided_by.endswith(":rapid")
        finally:
            object.__setattr__(aiperture.config.settings, "rapid_approval_window_seconds", original_window)
            object.__setattr__(aiperture.config.settings, "rapid_approval_min_count", original_count)
