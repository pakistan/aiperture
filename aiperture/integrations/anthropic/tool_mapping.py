"""Claude Code tool mapping — delegates to the canonical hooks implementation.

The full mapping logic lives in ``aiperture.hooks.tool_mapping`` since it
predates the integrations layer. This module wraps it in the ``ToolMapper``
protocol so it's consistent with the OpenAI and Google ADK mappers.
"""

from __future__ import annotations

from typing import Any

from aiperture.hooks.tool_mapping import map_tool


class ClaudeCodeToolMapper:
    """Map Claude Code tool calls to (tool, action, scope) triples.

    Delegates to ``aiperture.hooks.tool_mapping.map_tool``.
    """

    def map_tool(
        self, tool_name: str, tool_input: dict[str, Any],
    ) -> tuple[str, str, str] | None:
        return map_tool(tool_name, tool_input)
