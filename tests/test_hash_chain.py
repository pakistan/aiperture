"""Tests for audit trail hash chaining — tamper-evident logging."""

from sqlmodel import Session, select

from aiperture.db import get_engine
from aiperture.models.audit import AuditEvent
from aiperture.stores.audit_store import AuditStore, _GENESIS_HASH


class TestHashChaining:
    """Audit events should be hash-chained for tamper evidence."""

    def test_first_event_links_to_genesis(self):
        """First event should have previous_hash = genesis hash."""
        store = AuditStore()
        event = store.record("test.event", "First event")
        assert event.previous_hash == _GENESIS_HASH
        assert event.event_hash != ""
        assert len(event.event_hash) == 64  # SHA-256 hex

    def test_second_event_links_to_first(self):
        """Second event's previous_hash should equal first event's hash."""
        store = AuditStore()
        e1 = store.record("test.event", "First")
        e2 = store.record("test.event", "Second")
        assert e2.previous_hash == e1.event_hash

    def test_chain_of_five_events(self):
        """A chain of 5 events should link correctly."""
        store = AuditStore()
        events = []
        for i in range(5):
            e = store.record("test.event", f"Event {i}")
            events.append(e)

        for i in range(1, 5):
            assert events[i].previous_hash == events[i - 1].event_hash

    def test_verify_chain_valid(self):
        """verify_chain should return valid=True for an intact chain."""
        store = AuditStore()
        for i in range(5):
            store.record("test.event", f"Event {i}")

        result = store.verify_chain()
        assert result["valid"] is True
        assert result["verified"] == 5
        assert result["errors"] == []

    def test_verify_chain_detects_tampered_hash(self):
        """Modifying an event's data should break the hash chain."""
        store = AuditStore()
        for i in range(3):
            store.record("test.event", f"Event {i}")

        # Tamper: modify the summary of the second event via raw SQL
        from sqlalchemy import text
        with Session(get_engine()) as session:
            events = session.exec(
                select(AuditEvent).order_by(AuditEvent.id)
            ).all()
            event_id = events[1].id
            session.execute(
                text("UPDATE audit_events SET summary = 'TAMPERED' WHERE id = :id"),
                {"id": event_id},
            )
            session.commit()

        result = store.verify_chain()
        assert result["valid"] is False
        assert len(result["errors"]) >= 1
        assert any(e["error"] == "tampered_hash" for e in result["errors"])

    def test_verify_chain_detects_deleted_event(self):
        """Deleting an event should break the chain linkage."""
        store = AuditStore()
        for i in range(3):
            store.record("test.event", f"Event {i}")

        # Delete the middle event via raw SQL
        from sqlalchemy import text
        with Session(get_engine()) as session:
            events = session.exec(
                select(AuditEvent).order_by(AuditEvent.id)
            ).all()
            event_id = events[1].id
            session.execute(
                text("DELETE FROM audit_events WHERE id = :id"),
                {"id": event_id},
            )
            session.commit()

        result = store.verify_chain()
        assert result["valid"] is False
        assert any(e["error"] == "broken_chain" for e in result["errors"])

    def test_verify_empty_chain(self):
        """Empty audit trail should verify as valid."""
        store = AuditStore()
        result = store.verify_chain()
        assert result["valid"] is True
        assert result["total_events"] == 0

    def test_different_orgs_independent_chains(self):
        """Different organizations should have independent hash chains."""
        store = AuditStore()
        e1 = store.record("test.event", "Org A event", organization_id="org-a")
        e2 = store.record("test.event", "Org B event", organization_id="org-b")

        # Both should link to genesis (first in their org)
        assert e1.previous_hash == _GENESIS_HASH
        assert e2.previous_hash == _GENESIS_HASH

        # Both chains should be valid
        assert store.verify_chain("org-a")["valid"] is True
        assert store.verify_chain("org-b")["valid"] is True
