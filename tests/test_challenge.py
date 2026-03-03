"""Tests for HMAC challenge-response — prevents agent self-approval."""

import time

import pytest

from aperture.models.permission import Permission, PermissionDecision
from aperture.permissions.challenge import (
    create_challenge,
    reset_secret_for_testing,
    verify_challenge,
)
from aperture.permissions.engine import PermissionEngine


class TestChallengeModule:
    """Unit tests for challenge token creation and verification."""

    def test_create_returns_nonempty_token(self):
        token = create_challenge("shell", "execute", "ls")
        assert token.token
        assert token.nonce
        assert token.issued_at > 0

    def test_verify_valid_token(self):
        token = create_challenge("shell", "execute", "ls")
        assert verify_challenge(
            token=token.token,
            nonce=token.nonce,
            issued_at=token.issued_at,
            tool="shell",
            action="execute",
            scope="ls",
        )

    def test_reject_wrong_tool(self):
        token = create_challenge("shell", "execute", "ls")
        assert not verify_challenge(
            token=token.token,
            nonce=token.nonce,
            issued_at=token.issued_at,
            tool="filesystem",  # wrong
            action="execute",
            scope="ls",
        )

    def test_reject_wrong_scope(self):
        token = create_challenge("shell", "execute", "ls")
        assert not verify_challenge(
            token=token.token,
            nonce=token.nonce,
            issued_at=token.issued_at,
            tool="shell",
            action="execute",
            scope="rm -rf /",  # wrong
        )

    def test_reject_fabricated_token(self):
        assert not verify_challenge(
            token="fabricated_token_abc123",
            nonce="fake_nonce",
            issued_at=time.time(),
            tool="shell",
            action="execute",
            scope="ls",
        )

    def test_reject_empty_token(self):
        assert not verify_challenge(
            token="",
            nonce="",
            issued_at=0.0,
            tool="shell",
            action="execute",
            scope="ls",
        )

    def test_reject_expired_token(self):
        token = create_challenge("shell", "execute", "ls")
        assert not verify_challenge(
            token=token.token,
            nonce=token.nonce,
            issued_at=token.issued_at,
            tool="shell",
            action="execute",
            scope="ls",
            max_age_seconds=0.0,  # already expired
        )

    def test_different_nonces_per_call(self):
        t1 = create_challenge("shell", "execute", "ls")
        t2 = create_challenge("shell", "execute", "ls")
        assert t1.nonce != t2.nonce
        assert t1.token != t2.token

    def test_reset_secret_invalidates_old_tokens(self):
        token = create_challenge("shell", "execute", "ls")
        assert verify_challenge(
            token=token.token, nonce=token.nonce, issued_at=token.issued_at,
            tool="shell", action="execute", scope="ls",
        )
        reset_secret_for_testing()
        assert not verify_challenge(
            token=token.token, nonce=token.nonce, issued_at=token.issued_at,
            tool="shell", action="execute", scope="ls",
        )


class TestChallengeInEngine:
    """Integration tests: engine requires valid challenges for human decisions."""

    def test_approve_with_valid_challenge_succeeds(self):
        engine = PermissionEngine()
        # Get a verdict with challenge
        verdict = engine.check("shell", "execute", "deploy.sh", [])
        assert verdict.challenge  # DENY verdict should have challenge

        # Record with valid challenge
        engine.record_human_decision(
            tool="shell", action="execute", scope="deploy.sh",
            decision=PermissionDecision.ALLOW,
            decided_by="user-1",
            challenge=verdict.challenge,
            challenge_nonce=verdict.challenge_nonce,
            challenge_issued_at=verdict.challenge_issued_at,
        )

    def test_approve_without_challenge_raises(self):
        engine = PermissionEngine()
        with pytest.raises(ValueError, match="challenge"):
            engine.record_human_decision(
                tool="shell", action="execute", scope="deploy.sh",
                decision=PermissionDecision.ALLOW,
                decided_by="user-1",
                # no challenge provided
            )

    def test_approve_with_fabricated_challenge_raises(self):
        engine = PermissionEngine()
        with pytest.raises(ValueError, match="challenge"):
            engine.record_human_decision(
                tool="shell", action="execute", scope="deploy.sh",
                decision=PermissionDecision.ALLOW,
                decided_by="user-1",
                challenge="fabricated_token",
                challenge_nonce="fake_nonce",
                challenge_issued_at=time.time(),
            )

    def test_challenge_for_wrong_scope_raises(self):
        """Challenge for 'ls' cannot be used to approve 'rm -rf /'."""
        engine = PermissionEngine()
        verdict = engine.check("shell", "execute", "ls", [])

        with pytest.raises(ValueError, match="challenge"):
            engine.record_human_decision(
                tool="shell", action="execute", scope="rm -rf /",
                decision=PermissionDecision.ALLOW,
                decided_by="user-1",
                challenge=verdict.challenge,
                challenge_nonce=verdict.challenge_nonce,
                challenge_issued_at=verdict.challenge_issued_at,
            )

    def test_deny_verdict_has_challenge(self):
        engine = PermissionEngine()
        verdict = engine.check("shell", "execute", "anything", [])
        assert verdict.decision == "deny"
        assert verdict.challenge
        assert verdict.challenge_nonce
        assert verdict.challenge_issued_at > 0

    def test_allow_verdict_has_no_challenge(self):
        engine = PermissionEngine()
        rules = [Permission(tool="shell", action="execute", scope="*", decision=PermissionDecision.ALLOW)]
        verdict = engine.check("shell", "execute", "ls", rules)
        assert verdict.decision == "allow"
        assert not verdict.challenge

    def test_agent_cannot_self_approve_e2e(self):
        """Full flow: agent tries to self-approve without valid challenge — rejected."""
        engine = PermissionEngine()

        # Agent checks permission → gets DENY
        verdict = engine.check("shell", "execute", "rm -rf /", [])
        assert verdict.decision == "deny"

        # Agent tries to approve without challenge → rejected
        with pytest.raises(ValueError, match="challenge"):
            engine.record_human_decision(
                tool="shell", action="execute", scope="rm -rf /",
                decision=PermissionDecision.ALLOW,
                decided_by="user",
            )

        # Still denied
        verdict2 = engine.check("shell", "execute", "rm -rf /", [])
        assert verdict2.decision == "deny"
