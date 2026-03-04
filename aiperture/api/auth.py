"""Bearer token authentication for the AIperture HTTP API.

If AIPERTURE_API_KEY is empty or unset, all requests are allowed (local dev mode).
If set, every request must include an ``Authorization: Bearer <key>`` header
whose value matches the configured key exactly.

A plugin ``auth_backend`` can replace or extend the default bearer-token check.

The MCP server (stdio transport) is unaffected — this dependency is only wired
into the FastAPI application.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import aiperture.config
from aiperture import plugins

# optional=True so the scheme does not return 403 when the header is absent;
# we handle the missing-header case ourselves with a clear 401.
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """FastAPI dependency that enforces Bearer token auth when an API key is configured."""
    # Delegate to plugin auth backend if present
    auth_backend = plugins.get("auth_backend")
    if auth_backend is not None:
        await auth_backend.authenticate(request)
        return

    configured_key = aiperture.config.settings.api_key
    if not configured_key:
        # No key configured — open access (local dev mode).
        return

    if credentials is None or credentials.credentials != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
