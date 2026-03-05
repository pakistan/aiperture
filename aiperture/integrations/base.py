"""Base classes for runtime integrations.

Every runtime integration needs two things:
1. A ToolMapper — translates runtime-specific tool calls to (tool, action, scope)
2. A PermissionGuard — wraps tool execution with permission checks

This module provides the abstract contracts and a generic guard implementation
that works with any ToolMapper.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from aiperture.models.permission import PermissionDecision
from aiperture.models.verdict import RiskTier
from aiperture.permissions.engine import PermissionEngine, get_shared_engine
from aiperture.permissions.risk import classify_risk
from aiperture.stores.audit_store import AuditStore

logger = logging.getLogger(__name__)


class ToolMapper(Protocol):
    """Translate a runtime-specific tool call to an AIperture triple.

    Returns (tool, action, scope), or None to skip permission checking.
    """

    def map_tool(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[str, str, str] | None: ...


class PermissionGuard:
    """Generic permission guard for any runtime integration.

    Wraps the core PermissionEngine with runtime-specific tool mapping.
    Handles check → execute → record lifecycle.
    """

    def __init__(
        self,
        mapper: ToolMapper,
        runtime_id: str,
        *,
        organization_id: str = "default",
        engine: PermissionEngine | None = None,
    ):
        self.mapper = mapper
        self.runtime_id = runtime_id
        self.organization_id = organization_id
        self._engine = engine or get_shared_engine()
        self._audit = AuditStore()

    def check(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        *,
        session_id: str = "",
    ) -> PermissionDecision | None:
        """Check permission for a tool call.

        Returns:
            PermissionDecision.ALLOW — proceed with execution
            PermissionDecision.DENY — block execution
            PermissionDecision.ASK — runtime should prompt the user
            None — tool was skipped (e.g. AIperture's own tools)
        """
        mapping = self.mapper.map_tool(tool_name, tool_input)
        if mapping is None:
            return None

        tool, action, scope = mapping

        verdict = self._engine.check(
            tool=tool,
            action=action,
            scope=scope,
            permissions=[],
            session_id=session_id,
            organization_id=self.organization_id,
            runtime_id=self.runtime_id,
        )

        return verdict.decision

    def record_approval(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        *,
        session_id: str = "",
    ) -> bool:
        """Record that a tool call was approved (by the runtime's permission UI).

        Call this after the tool executes successfully and the user approved it
        through the runtime's own permission mechanism.

        Returns True if recorded, False if skipped.
        """
        mapping = self.mapper.map_tool(tool_name, tool_input)
        if mapping is None:
            return False

        tool, action, scope = mapping

        # Never auto-approve HIGH/CRITICAL risk in future
        risk = classify_risk(tool, action, scope)
        if risk.tier in (RiskTier.HIGH, RiskTier.CRITICAL):
            logger.debug(
                "Skipping approval record for %s.%s on %s — risk tier %s",
                tool, action, scope, risk.tier.value,
            )

        self._engine.record_hook_decision(
            tool=tool,
            action=action,
            scope=scope,
            decision=PermissionDecision.ALLOW,
            session_id=session_id,
            organization_id=self.organization_id,
            runtime_id=self.runtime_id,
        )

        self._audit.record(
            "integration.approval",
            f"Approved {tool}.{action} on {scope}",
            entity_type="permission",
            entity_id=f"{tool}.{action}",
            actor_id=f"{self.runtime_id}-hook",
            actor_type="hook",
            runtime_id=self.runtime_id,
            details={"tool": tool, "action": action, "scope": scope},
        )

        return True

    def record_denial(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        *,
        session_id: str = "",
    ) -> bool:
        """Record that a tool call was denied by the user.

        Returns True if recorded, False if skipped.
        """
        mapping = self.mapper.map_tool(tool_name, tool_input)
        if mapping is None:
            return False

        tool, action, scope = mapping

        self._engine.record_hook_decision(
            tool=tool,
            action=action,
            scope=scope,
            decision=PermissionDecision.DENY,
            session_id=session_id,
            organization_id=self.organization_id,
            runtime_id=self.runtime_id,
        )

        return True
