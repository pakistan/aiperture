"""Tests for HMAC nonce persistence across server restarts."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from aiperture.db import get_engine
from aiperture.models.permission import ConsumedNonce
from aiperture.permissions.challenge import (
    _consumed_nonces,
    _nonce_lock,
    cleanup_expired_nonces,
    create_challenge,
    reset_secret_for_testing,
    verify_challenge,
)


class TestNoncePersistence:
    """Nonces should be persisted to DB for replay protection."""

    def setup_method(self):
        reset_secret_for_testing()

    def test_verified_nonce_stored_in_db(self):
        """After verification, nonce should exist in database."""
        ch = create_challenge("filesystem", "read", "test.py")
        assert verify_challenge(
            ch.token, ch.nonce, ch.issued_at,
            "filesystem", "read", "test.py",
        )
        # Check DB
        with Session(get_engine()) as session:
            record = session.get(ConsumedNonce, ch.nonce)
            assert record is not None
            assert record.nonce == ch.nonce

    def test_replay_after_memory_clear_rejected(self):
        """Simulate server restart: clear memory, nonce should still be rejected via DB."""
        ch = create_challenge("filesystem", "read", "test.py")
        assert verify_challenge(
            ch.token, ch.nonce, ch.issued_at,
            "filesystem", "read", "test.py",
        )
        # Simulate restart: clear in-memory cache
        with _nonce_lock:
            _consumed_nonces.clear()

        # Replay should be rejected (found in DB)
        assert not verify_challenge(
            ch.token, ch.nonce, ch.issued_at,
            "filesystem", "read", "test.py",
        )

    def test_normal_flow_still_works(self):
        """Normal challenge-verify flow should work end-to-end."""
        ch = create_challenge("shell", "execute", "ls -la", organization_id="org1", session_id="s1")
        assert verify_challenge(
            ch.token, ch.nonce, ch.issued_at,
            "shell", "execute", "ls -la",
            organization_id="org1", session_id="s1",
        )

    def test_cleanup_removes_expired_nonces(self):
        """cleanup_expired_nonces should remove old nonces from DB."""
        # Insert an old nonce directly
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        with Session(get_engine()) as session:
            session.add(ConsumedNonce(nonce="old-nonce-123", consumed_at=old_time))
            session.commit()

        removed = cleanup_expired_nonces()
        assert removed >= 1

        # Verify it's gone
        with Session(get_engine()) as session:
            assert session.get(ConsumedNonce, "old-nonce-123") is None

    def test_fresh_nonce_not_cleaned(self):
        """Recent nonces should NOT be cleaned up."""
        ch = create_challenge("filesystem", "read", "keep.py")
        verify_challenge(
            ch.token, ch.nonce, ch.issued_at,
            "filesystem", "read", "keep.py",
        )
        removed = cleanup_expired_nonces()
        # Fresh nonce should still be in DB
        with Session(get_engine()) as session:
            assert session.get(ConsumedNonce, ch.nonce) is not None
