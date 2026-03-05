"""Permission guard for OpenAI function calling.

Works with both the OpenAI Python client and the Agents SDK.
"""

from __future__ import annotations

from typing import Any

from aiperture.integrations.base import PermissionGuard
from aiperture.integrations.openai.tool_mapping import OpenAIToolMapper


class OpenAIPermissionGuard(PermissionGuard):
    """Permission guard for OpenAI function calls.

    Usage::

        guard = OpenAIPermissionGuard()

        decision = guard.check("get_weather", {"location": "NYC"})
        if decision == PermissionDecision.ALLOW:
            result = get_weather(location="NYC")
            guard.record_approval("get_weather", {"location": "NYC"})
    """

    def __init__(
        self,
        *,
        organization_id: str = "default",
        **kwargs: Any,
    ):
        super().__init__(
            mapper=OpenAIToolMapper(),
            runtime_id="openai",
            organization_id=organization_id,
            **kwargs,
        )
