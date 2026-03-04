"""Permission models — RBAC + ReBAC for AI agent actions."""

import enum
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class PermissionDecision(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Permission(BaseModel):
    """Static permission rule. Scopes use glob patterns (fnmatch)."""

    tool: str
    action: str
    scope: str  # glob pattern, e.g. "src/*.py", "database.*"
    decision: PermissionDecision


class PermissionLog(SQLModel, table=True):
    """Immutable record of every permission decision. Append-only."""

    __tablename__ = "permission_logs"
    __table_args__ = (
        Index("ix_permlog_org_tool_action", "organization_id", "tool", "action"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: str = Field(default="default", index=True)
    task_id: str = Field(default="", index=True)
    session_id: str = Field(default="", index=True)
    tool: str
    action: str
    scope: str
    decision: str  # PermissionDecision value
    decided_by: str  # "system", "human:<user_id>", "auto_learned"
    context_summary: str = ""
    resource: str = Field(default="", index=True)  # normalized target (intent-based matching)
    runtime_id: str = Field(default="", index=True)  # which external runtime asked
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    revoked_at: datetime | None = Field(default=None)  # soft-delete for revocation


class ConsumedNonce(SQLModel, table=True):
    """Persisted HMAC nonces for replay protection across server restarts."""

    __tablename__ = "consumed_nonces"

    nonce: str = Field(primary_key=True)
    consumed_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))


class TaskPermissionStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"
    REVOKED = "revoked"
    DENIED = "denied"


class TaskPermission(SQLModel, table=True):
    """Task-scoped permission grant (ReBAC). TTL-expirable."""

    __tablename__ = "task_permissions"

    id: int | None = Field(default=None, primary_key=True)
    permission_id: str = Field(index=True)  # unique ID for this grant
    task_id: str = Field(index=True)
    organization_id: str = Field(default="default", index=True)
    tool: str
    action: str
    scope: str
    decision: str  # PermissionDecision value
    status: str = TaskPermissionStatus.ACTIVE
    granted_by: str = ""
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
