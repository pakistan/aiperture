"""Project auto-detection — determines project_id from environment.

Detection priority:
1. AIPERTURE_PROJECT_ID env var (explicit override)
2. Git remote origin → owner/repo (stable, portable)
3. Git toplevel directory name (no remote)
4. "global" fallback (non-git directories)

Reserved value: "global" — user-wide cross-project patterns.
"""

import logging
import subprocess
from functools import lru_cache

logger = logging.getLogger(__name__)

GLOBAL_PROJECT_ID = "global"


@lru_cache(maxsize=1)
def detect_project_id() -> str:
    """Auto-detect the current project ID."""
    import aiperture.config

    explicit = aiperture.config.settings.project_id
    if explicit:
        return explicit

    # Try git remote origin
    remote = _git_remote_origin()
    if remote:
        return remote

    # Try git toplevel directory name
    toplevel = _git_toplevel_name()
    if toplevel:
        return toplevel

    return GLOBAL_PROJECT_ID


def _git_remote_origin() -> str | None:
    """Extract owner/repo from git remote origin URL."""
    try:
        url = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return None

    if not url:
        return None

    # SSH: git@github.com:owner/repo.git
    if ":" in url and "@" in url:
        path = url.split(":")[-1]
    # HTTPS: https://github.com/owner/repo.git
    elif "/" in url:
        # Strip protocol + host
        parts = url.split("/")
        # Take last two parts: owner/repo
        path = "/".join(parts[-2:])
    else:
        return None

    # Strip .git suffix
    if path.endswith(".git"):
        path = path[:-4]

    return path or None


def _git_toplevel_name() -> str | None:
    """Get the git repository root directory name."""
    try:
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return None

    if not toplevel:
        return None

    # Use just the directory name
    import os.path
    return os.path.basename(toplevel) or None
