"""OpenAI Agents SDK guardrail integration.

Provides an input guardrail that checks AIperture permissions before
tool execution, and a decorator for wrapping individual tool functions.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from aiperture.integrations.openai.guard import OpenAIPermissionGuard
from aiperture.models.permission import PermissionDecision

logger = logging.getLogger(__name__)


class AipertureGuardrail:
    """OpenAI Agents SDK input guardrail backed by AIperture.

    Add this to an Agent's ``input_guardrails`` to gate tool calls through
    AIperture's permission engine::

        from agents import Agent
        from aiperture.integrations.openai import AipertureGuardrail

        agent = Agent(
            name="my-agent",
            tools=[my_tool],
            input_guardrails=[AipertureGuardrail()],
        )

    The guardrail intercepts tool calls, checks AIperture, and raises
    ``InputGuardrailTripwireTriggered`` if the action is denied.
    """

    def __init__(
        self,
        *,
        organization_id: str = "default",
        session_id: str = "",
    ):
        self.guard = OpenAIPermissionGuard(organization_id=organization_id)
        self.session_id = session_id

    async def run(self, input_data: Any, context: Any) -> Any:
        """Guardrail entry point called by the Agents SDK.

        The Agents SDK calls this before executing tools. We inspect the
        input for tool calls and check each against AIperture.
        """
        # The Agents SDK guardrail protocol passes the agent input.
        # Tool-level guardrails get the tool name and arguments.
        tool_name = getattr(input_data, "tool_name", None) or getattr(input_data, "name", None)
        tool_input = getattr(input_data, "tool_input", None) or getattr(input_data, "arguments", {})

        if not tool_name:
            return None  # Not a tool call, pass through

        if isinstance(tool_input, str):
            import json
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, TypeError):
                tool_input = {"raw": tool_input}

        session_id = self.session_id or getattr(context, "session_id", "")

        decision = self.guard.check(
            tool_name,
            tool_input,
            session_id=session_id,
        )

        if decision == PermissionDecision.DENY:
            logger.warning(
                "AIperture denied: %s with %s", tool_name, tool_input,
            )
            # Import here to avoid hard dependency on agents SDK at module level
            try:
                from agents import InputGuardrailTripwireTriggered
                raise InputGuardrailTripwireTriggered(
                    f"AIperture denied: {tool_name}",
                )
            except ImportError:
                raise PermissionError(f"AIperture denied: {tool_name}")

        if decision == PermissionDecision.ALLOW:
            logger.debug("AIperture auto-approved: %s", tool_name)

        # ASK or None — let the runtime handle it
        return None


def aiperture_guard(
    *,
    session_id: str = "",
    organization_id: str = "default",
) -> Callable:
    """Decorator that gates a tool function through AIperture.

    Usage::

        @aiperture_guard(session_id="my-session")
        def read_file(path: str) -> str:
            return open(path).read()

    If AIperture denies the call, raises PermissionError.
    If AIperture approves, executes and records the approval.
    """
    guard = OpenAIPermissionGuard(organization_id=organization_id)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tool_input = kwargs.copy()
            decision = guard.check(func.__name__, tool_input, session_id=session_id)

            if decision == PermissionDecision.DENY:
                raise PermissionError(f"AIperture denied: {func.__name__}")

            result = func(*args, **kwargs)

            if decision in (PermissionDecision.ALLOW, PermissionDecision.ASK):
                guard.record_approval(func.__name__, tool_input, session_id=session_id)

            return result

        return wrapper
    return decorator
