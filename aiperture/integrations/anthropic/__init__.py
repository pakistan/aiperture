"""Anthropic Claude Code integration for AIperture.

Claude Code has the deepest integration via native hooks
(PermissionRequest + PostToolUse) in ``aiperture.hooks`` and
``aiperture.api.routes.hooks``. This module provides:

1. A ``ClaudeCodePermissionGuard`` that follows the same interface as
   the OpenAI and Google ADK guards, for programmatic use outside the
   hook flow.
2. Re-exports the hook tool mapper so all runtime mappers are
   discoverable under ``aiperture.integrations.*``.

Hook-based integration (recommended for Claude Code CLI)::

    # Configured via `aiperture setup-claude` — no code needed.
    # Hooks call POST /hooks/permission-request and /hooks/post-tool-use.

Programmatic integration (API or SDK usage)::

    from aiperture.integrations.anthropic import ClaudeCodePermissionGuard
    from aiperture.models.permission import PermissionDecision

    guard = ClaudeCodePermissionGuard()

    decision = guard.check("Bash", {"command": "git status"})
    if decision == PermissionDecision.ALLOW:
        result = run_bash("git status")
        guard.record_approval("Bash", {"command": "git status"})
"""

from aiperture.integrations.anthropic.guard import ClaudeCodePermissionGuard
from aiperture.hooks.tool_mapping import map_tool as claude_code_map_tool

__all__ = ["ClaudeCodePermissionGuard", "claude_code_map_tool"]
