"""OpenAI Agents SDK integration for AIperture.

Usage with OpenAI Agents SDK::

    from agents import Agent, Runner
    from aiperture.integrations.openai import AipertureGuardrail

    guardrail = AipertureGuardrail()

    agent = Agent(
        name="my-agent",
        tools=[my_tool],
        input_guardrails=[guardrail],
    )

Usage as a decorator for standalone tool functions::

    from aiperture.integrations.openai import aiperture_guard

    @aiperture_guard(session_id="my-session")
    def my_tool(query: str) -> str:
        return do_something(query)

Usage with the OpenAI Python client (function calling)::

    from aiperture.integrations.openai import OpenAIPermissionGuard

    guard = OpenAIPermissionGuard()

    # Before executing a function call from the model
    decision = guard.check("get_weather", {"location": "NYC"})
    if decision == PermissionDecision.ALLOW:
        result = get_weather(location="NYC")
        guard.record_approval("get_weather", {"location": "NYC"})
"""

from aiperture.integrations.openai.guardrail import AipertureGuardrail, aiperture_guard
from aiperture.integrations.openai.guard import OpenAIPermissionGuard

__all__ = ["AipertureGuardrail", "OpenAIPermissionGuard", "aiperture_guard"]
