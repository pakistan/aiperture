"""HMAC challenge-response for human decision verification.

When check_permission returns DENY or ASK, the verdict includes a challenge
token (HMAC-SHA256 signed with a server-side secret). approve_action and
deny_action must present this token to record a decision.

The agent cannot forge the token because the secret is generated at server
startup and never exposed via MCP, REST, or logs.
"""

import hashlib
import hmac
import os
import time
from dataclasses import dataclass

# Server-side secret — generated once at import time, never exposed
_SERVER_SECRET: bytes = os.urandom(32)

# Default max age: 1 hour
DEFAULT_MAX_AGE_SECONDS = 3600.0


@dataclass
class ChallengeToken:
    """An HMAC challenge bound to a specific permission check."""

    token: str  # hex-encoded HMAC
    nonce: str  # unique per-check
    issued_at: float  # time.time()
    tool: str
    action: str
    scope: str


def create_challenge(tool: str, action: str, scope: str) -> ChallengeToken:
    """Create an HMAC challenge for a permission check."""
    nonce = os.urandom(16).hex()
    issued_at = time.time()
    message = f"{tool}|{action}|{scope}|{nonce}|{issued_at}".encode()
    token = hmac.new(_SERVER_SECRET, message, hashlib.sha256).hexdigest()
    return ChallengeToken(
        token=token,
        nonce=nonce,
        issued_at=issued_at,
        tool=tool,
        action=action,
        scope=scope,
    )


def verify_challenge(
    token: str,
    nonce: str,
    issued_at: float,
    tool: str,
    action: str,
    scope: str,
    *,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
) -> bool:
    """Verify an HMAC challenge token.

    Returns True if the token is valid and not expired.
    """
    if not token or not nonce:
        return False

    # Check expiry
    if time.time() - issued_at > max_age_seconds:
        return False

    # Recompute HMAC
    message = f"{tool}|{action}|{scope}|{nonce}|{issued_at}".encode()
    expected = hmac.new(_SERVER_SECRET, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(token, expected)


def reset_secret_for_testing() -> None:
    """Reset the server secret. ONLY for use in tests."""
    global _SERVER_SECRET
    _SERVER_SECRET = os.urandom(32)
