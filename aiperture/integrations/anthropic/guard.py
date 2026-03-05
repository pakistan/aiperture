"""Permission guard for Claude Code.

For most Claude Code users, the hook-based integration (``aiperture setup-claude``)
is the recommended path — it learns from Claude Code's native permission dialog
with zero code changes.

This guard is for programmatic use cases: calling Claude Code via the API,
building custom wrappers, or testing.
"""

from __future__ import annotations

from typing import Any

from aiperture.integrations.base import PermissionGuard
from aiperture.integrations.anthropic.tool_mapping import ClaudeCodeToolMapper


class ClaudeCodePermissionGuard(PermissionGuard):
    """Permission guard for Claude Code tool calls.

    Uses the same tool mapping as the hook endpoints, wrapped in the
    standard ``PermissionGuard`` interface.

    Usage::

        guard = ClaudeCodePermissionGuard()

        decision = guard.check("Bash", {"command": "git status"})
        if decision == PermissionDecision.ALLOW:
            result = run_tool("Bash", command="git status")
            guard.record_approval("Bash", {"command": "git status"})
    """

    def __init__(
        self,
        *,
        organization_id: str = "default",
        **kwargs: Any,
    ):
        super().__init__(
            mapper=ClaudeCodeToolMapper(),
            runtime_id="claude-code",
            organization_id=organization_id,
            **kwargs,
        )
