"""Scope normalization --- groups related scopes to accelerate learning.

"git log --oneline -5" -> "git log*"
"src/components/Button.tsx" -> "src/components/*.tsx"

Normalized scopes require higher thresholds than exact matches.
"""

import fnmatch
import re
import shlex

# Commands with recognized subcommands
_SUBCOMMAND_CMDS: dict[str, frozenset[str]] = {
    "git": frozenset(
        {
            "status",
            "log",
            "diff",
            "show",
            "branch",
            "checkout",
            "commit",
            "push",
            "pull",
            "fetch",
            "merge",
            "rebase",
            "stash",
            "tag",
            "add",
            "reset",
            "remote",
            "clone",
            "init",
        }
    ),
    "npm": frozenset(
        {
            "test",
            "run",
            "install",
            "start",
            "build",
            "list",
            "show",
            "init",
            "publish",
            "audit",
            "outdated",
        }
    ),
    "docker": frozenset(
        {
            "build",
            "run",
            "exec",
            "ps",
            "images",
            "pull",
            "push",
            "stop",
            "start",
            "restart",
            "rm",
            "rmi",
            "logs",
            "compose",
        }
    ),
    "kubectl": frozenset(
        {
            "get",
            "describe",
            "apply",
            "delete",
            "logs",
            "exec",
            "create",
            "edit",
            "scale",
            "rollout",
        }
    ),
    "pip": frozenset(
        {
            "install",
            "uninstall",
            "list",
            "show",
            "freeze",
            "search",
        }
    ),
    "cargo": frozenset(
        {
            "build",
            "test",
            "run",
            "check",
            "clippy",
            "fmt",
            "doc",
            "new",
            "init",
            "publish",
        }
    ),
    "make": frozenset(),  # make targets are arbitrary, just keep "make*"
}

# File extension pattern
_EXT_RE = re.compile(r"\.\w{1,10}$")


def normalize_scope(tool: str, action: str, scope: str) -> str | None:
    """Normalize a scope to its "group" pattern.

    Returns None if the scope cannot be meaningfully normalized
    (already a glob, too short, or too dangerous to generalize).

    Args:
        tool: Tool name
        action: Action name
        scope: Raw scope string

    Returns:
        Normalized glob pattern, or None if not normalizable.
    """
    if not scope or "*" in scope or "?" in scope:
        return None  # Already a glob or empty

    # Skip normalization for sensitive paths — require exact-match learning
    if _is_sensitive(scope):
        return None

    tool_lower = tool.lower()
    if tool_lower in ("shell", "bash", "terminal"):
        return _normalize_shell_scope(scope)
    elif tool_lower in ("filesystem", "file", "fs"):
        return _normalize_filesystem_scope(scope)

    return None


def _normalize_shell_scope(scope: str) -> str | None:
    """Normalize a shell command scope.

    Rules:
    - Extract the base command (first word)
    - If the command has subcommands (git log, npm test), keep the subcommand
    - Strip all flags and arguments
    - Append * to indicate "any arguments"

    Examples:
        "git log --oneline -5" -> "git log*"
        "git status" -> "git status*"
        "npm test -- --watch" -> "npm test*"
        "ls -la /home/user" -> "ls*"
        "pytest tests/test_foo.py -v" -> "pytest*"
    """
    try:
        parts = shlex.split(scope)
    except ValueError:
        parts = scope.split()

    if not parts:
        return None

    cmd = parts[0].lower()

    # Check for subcommand commands
    if cmd in _SUBCOMMAND_CMDS and len(parts) > 1:
        subcmd = parts[1].lower()
        known_subcmds = _SUBCOMMAND_CMDS[cmd]
        if not known_subcmds or subcmd in known_subcmds:
            # Keep cmd + subcommand
            return f"{parts[0]} {parts[1]}*"

    # Single command --- just base + *
    return f"{parts[0]}*"


def _normalize_filesystem_scope(scope: str) -> str | None:
    """Normalize a filesystem scope to a directory+extension pattern.

    Rules:
    - Extract the directory and file extension
    - Replace the filename with *
    - Keep the extension

    Examples:
        "src/components/Button.tsx" -> "src/components/*.tsx"
        "docs/guide.md" -> "docs/*.md"
        "config.yaml" -> "*.yaml"
        "src/**/*.py" -> None (already a glob)
    """
    # Skip normalization for sensitive filesystem paths
    if _is_sensitive(scope):
        return None

    # Must have an extension to normalize
    ext_match = _EXT_RE.search(scope)
    if not ext_match:
        return None

    ext = ext_match.group()

    # Split into directory and filename
    if "/" in scope:
        last_slash = scope.rindex("/")
        directory = scope[:last_slash]
        return f"{directory}/*{ext}"
    else:
        return f"*{ext}"


def _is_sensitive(scope: str) -> bool:
    """Check if scope matches any sensitive pattern from config.

    Sensitive paths skip normalization so they require exact-match learning
    (e.g., 10 approvals of `src/secrets.py` specifically, not `src/*.py`).
    """
    import aiperture.config

    # Extract just the filename for matching (handle paths like "src/config/secrets.py")
    filename = scope.rsplit("/", 1)[-1] if "/" in scope else scope

    for pattern in aiperture.config.settings.sensitive_patterns_list:
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(scope, pattern):
            return True
    return False
