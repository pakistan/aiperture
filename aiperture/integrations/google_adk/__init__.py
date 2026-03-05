"""Google ADK (Agent Development Kit) integration for AIperture.

Usage with Google ADK::

    from google.adk import Agent
    from aiperture.integrations.google_adk import ADKPermissionGuard

    guard = ADKPermissionGuard()

    # Before executing a tool call
    decision = guard.check("search_web", {"query": "AI safety"})
    if decision == PermissionDecision.ALLOW:
        result = search_web(query="AI safety")
        guard.record_approval("search_web", {"query": "AI safety"})
"""

from aiperture.integrations.google_adk.guard import ADKPermissionGuard

__all__ = ["ADKPermissionGuard"]
