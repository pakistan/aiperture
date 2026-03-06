"""Audit event model — append-only log of everything that happens."""

from datetime import UTC, datetime

from sqlmodel import JSON, Column, Field, SQLModel


class AuditEvent(SQLModel, table=True):
    """Immutable audit trail entry. Never deleted, never modified."""

    __tablename__ = "audit_events"

    id: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(index=True, unique=True)
    organization_id: str = Field(default="default", index=True)
    project_id: str = Field(default="global", index=True)
    batch_id: str = Field(default="", index=True)

    # What happened
    event_type: str = Field(index=True)  # "permission.check", "artifact.stored", etc.
    entity_type: str = Field(default="", index=True)  # "task", "artifact", "permission"
    entity_id: str = Field(default="", index=True)
    summary: str = ""

    # Who did it
    actor_id: str = Field(default="", index=True)
    actor_type: str = ""  # "runtime", "human", "system"
    runtime_id: str = Field(default="", index=True)

    # State change
    details: dict | None = Field(default=None, sa_column=Column(JSON))
    previous_state: dict | None = Field(default=None, sa_column=Column(JSON))
    new_state: dict | None = Field(default=None, sa_column=Column(JSON))

    # Hash chain for tamper-evident audit trail
    previous_hash: str = Field(default="")
    event_hash: str = Field(default="")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
