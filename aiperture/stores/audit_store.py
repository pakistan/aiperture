"""Audit store — append-only event log. Never deletes. Never modifies.

Every permission check, every artifact stored, every human decision
gets an audit event. This is the compliance backbone.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from aiperture.db import get_engine
from aiperture.models.audit import AuditEvent

_GENESIS_HASH = "0" * 64  # sentinel for the first event in the chain

logger = logging.getLogger(__name__)


class AuditStore:
    """Append-only audit trail."""

    def record(
        self,
        event_type: str,
        summary: str,
        *,
        organization_id: str = "default",
        project_id: str = "global",
        entity_type: str = "",
        entity_id: str = "",
        actor_id: str = "",
        actor_type: str = "",
        runtime_id: str = "",
        details: dict | None = None,
        previous_state: dict | None = None,
        new_state: dict | None = None,
        batch_id: str = "",
    ) -> AuditEvent:
        """Record an audit event. Fire-and-forget — never breaks the caller."""
        event = AuditEvent(
            event_id=uuid.uuid4().hex[:16],
            organization_id=organization_id,
            project_id=project_id,
            batch_id=batch_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            actor_id=actor_id,
            actor_type=actor_type,
            runtime_id=runtime_id,
            details=details,
            previous_state=previous_state,
            new_state=new_state,
        )
        try:
            with Session(get_engine()) as session:
                # Hash chaining: link to previous event
                prev = session.exec(
                    select(AuditEvent)
                    .where(AuditEvent.organization_id == event.organization_id)
                    .order_by(AuditEvent.id.desc())  # type: ignore[union-attr]
                    .limit(1)
                ).first()
                event.previous_hash = prev.event_hash if (prev and prev.event_hash) else _GENESIS_HASH
                event.event_hash = _compute_event_hash(event)

                session.add(event)
                session.commit()
                session.refresh(event)
                session.expunge(event)
            # Notify audit hook plugin (fire-and-forget)
            from aiperture import plugins

            audit_hook = plugins.get("audit_hook")
            if audit_hook is not None:
                try:
                    audit_hook.on_audit_event(event)
                except Exception:
                    logger.debug("Audit hook failed", exc_info=True)
        except Exception:
            logger.error("Failed to record audit event: %s", event_type, exc_info=True)
        return event

    def list_events(
        self,
        organization_id: str = "default",
        *,
        event_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor_id: str | None = None,
        runtime_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events with filters."""
        with Session(get_engine()) as session:
            query = select(AuditEvent).where(
                AuditEvent.organization_id == organization_id,
            )
            if event_type:
                query = query.where(AuditEvent.event_type == event_type)
            if entity_type:
                query = query.where(AuditEvent.entity_type == entity_type)
            if entity_id:
                query = query.where(AuditEvent.entity_id == entity_id)
            if actor_id:
                query = query.where(AuditEvent.actor_id == actor_id)
            if runtime_id:
                query = query.where(AuditEvent.runtime_id == runtime_id)
            if since:
                query = query.where(AuditEvent.created_at >= since)  # type: ignore[operator]
            if until:
                query = query.where(AuditEvent.created_at <= until)  # type: ignore[operator]

            query = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)  # type: ignore[union-attr]
            results = session.exec(query).all()
            for r in results:
                session.expunge(r)
            return list(results)

    def get_event(self, event_id: str) -> AuditEvent | None:
        """Get a single audit event."""
        with Session(get_engine()) as session:
            result = session.exec(
                select(AuditEvent).where(AuditEvent.event_id == event_id)
            ).first()
            if result:
                session.expunge(result)
            return result

    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        organization_id: str = "default",
        limit: int = 50,
    ) -> list[AuditEvent]:
        """Get full history of an entity."""
        with Session(get_engine()) as session:
            results = session.exec(
                select(AuditEvent).where(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.entity_type == entity_type,
                    AuditEvent.entity_id == entity_id,
                ).order_by(AuditEvent.created_at.desc()).limit(limit)  # type: ignore[union-attr]
            ).all()
            for r in results:
                session.expunge(r)
            return list(results)

    def count(self, organization_id: str = "default") -> int:
        """Count total audit events."""
        with Session(get_engine()) as session:
            result = session.exec(
                select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.organization_id == organization_id,
                )
            ).one()
            return result

    def verify_chain(self, organization_id: str = "default") -> dict:
        """Verify the hash chain integrity of the audit trail.

        Walks the chain and checks that each event's hash matches its
        computed value and links to the previous event's hash.

        Returns a dict with verification results.
        """
        with Session(get_engine()) as session:
            events = session.exec(
                select(AuditEvent)
                .where(AuditEvent.organization_id == organization_id)
                .order_by(AuditEvent.id.asc())  # type: ignore[union-attr]
            ).all()

        if not events:
            return {"valid": True, "total_events": 0, "verified": 0, "errors": []}

        errors = []
        verified = 0
        prev_hash = _GENESIS_HASH

        for event in events:
            # Skip events without hash chain (pre-migration)
            if not event.event_hash:
                prev_hash = _GENESIS_HASH
                continue

            # Check previous_hash links correctly
            if event.previous_hash and event.previous_hash != prev_hash:
                errors.append({
                    "event_id": event.event_id,
                    "error": "broken_chain",
                    "expected_previous": prev_hash,
                    "actual_previous": event.previous_hash,
                })

            # Recompute and verify event hash
            expected_hash = _compute_event_hash(event)
            if event.event_hash != expected_hash:
                errors.append({
                    "event_id": event.event_id,
                    "error": "tampered_hash",
                    "expected": expected_hash,
                    "actual": event.event_hash,
                })

            prev_hash = event.event_hash
            verified += 1

        return {
            "valid": len(errors) == 0,
            "total_events": len(events),
            "verified": verified,
            "errors": errors,
        }


def _compute_event_hash(event: AuditEvent) -> str:
    """Compute SHA-256 hash for an audit event."""
    details_json = json.dumps(event.details, sort_keys=True, default=str) if event.details else ""
    payload = (
        f"{event.previous_hash}|{event.event_id}|{event.event_type}|"
        f"{event.created_at.isoformat()}|{event.summary}|{details_json}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()
