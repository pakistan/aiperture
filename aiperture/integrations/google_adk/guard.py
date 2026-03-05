"""Permission guard for Google ADK."""

from __future__ import annotations

from typing import Any

from aiperture.integrations.base import PermissionGuard
from aiperture.integrations.google_adk.tool_mapping import ADKToolMapper


class ADKPermissionGuard(PermissionGuard):
    """Permission guard for Google ADK function calls.

    Usage::

        guard = ADKPermissionGuard()

        decision = guard.check("search_web", {"query": "AI safety"})
        if decision == PermissionDecision.ALLOW:
            result = search_web(query="AI safety")
            guard.record_approval("search_web", {"query": "AI safety"})
    """

    def __init__(
        self,
        *,
        organization_id: str = "default",
        **kwargs: Any,
    ):
        super().__init__(
            mapper=ADKToolMapper(),
            runtime_id="google-adk",
            organization_id=organization_id,
            **kwargs,
        )
