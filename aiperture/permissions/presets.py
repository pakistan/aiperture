"""Bootstrap presets -- seed permission decisions to eliminate day-1 denial storms.

Presets provide synthetic human:bootstrap decisions so that the learning engine
auto-approves common safe patterns immediately, without requiring a real human
to approve each one individually.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session

import aiperture.config
from aiperture.db import get_engine
from aiperture.models.permission import PermissionDecision, PermissionLog


@dataclass
class PresetDecision:
    """A single pre-approved permission pattern."""

    tool: str
    action: str
    scope: str


# ---------------------------------------------------------------------------
# Preset: readonly -- filesystem reads and safe shell commands
# ---------------------------------------------------------------------------

_FILESYSTEM_READ_EXTENSIONS = [
    "*.py", "*.js", "*.ts", "*.tsx", "*.jsx",
    "*.json", "*.yaml", "*.yml", "*.toml", "*.cfg", "*.ini",
    "*.md", "*.txt", "*.rst", "*.csv",
    "*.html", "*.css", "*.scss",
    "*.sh", "*.bash", "*.zsh",
    "*.go", "*.rs", "*.java", "*.c", "*.cpp", "*.h",
    "*.rb", "*.php", "*.swift", "*.kt",
    "*.xml", "*.sql", "*.graphql",
    "*.env.example", "*.gitignore", "*.dockerignore",
    "Makefile", "Dockerfile", "Cargo.toml", "package.json",
]

_SAFE_SHELL_COMMANDS = [
    "ls*", "cat*", "head*", "tail*", "wc*",
    "find*", "grep*", "rg*",
    "which*", "pwd*", "whoami*",
    "echo*", "date*", "env*",
]

PRESET_READONLY: list[PresetDecision] = [
    PresetDecision(tool="filesystem", action="read", scope=ext)
    for ext in _FILESYSTEM_READ_EXTENSIONS
] + [
    PresetDecision(tool="shell", action="execute", scope=cmd)
    for cmd in _SAFE_SHELL_COMMANDS
]

# ---------------------------------------------------------------------------
# Preset: developer -- extends readonly with git, test runners, diagnostics
# ---------------------------------------------------------------------------

_GIT_READONLY_COMMANDS = [
    "git status*", "git log*", "git diff*", "git show*",
    "git branch*", "git remote*", "git tag*", "git stash list*",
]

_TEST_RUNNER_COMMANDS = [
    "pytest*", "npm test*", "cargo test*", "go test*", "make test*",
]

_DIAGNOSTIC_COMMANDS = [
    "npm list*", "pip list*", "pip show*",
    "python --version*", "node --version*", "npm --version*",
    "cargo --version*", "go version*", "rustc --version*",
    "ruff*", "eslint*", "mypy*", "black --check*", "flake8*",
]

PRESET_DEVELOPER: list[PresetDecision] = PRESET_READONLY + [
    PresetDecision(tool="shell", action="execute", scope=cmd)
    for cmd in _GIT_READONLY_COMMANDS + _TEST_RUNNER_COMMANDS + _DIAGNOSTIC_COMMANDS
]

# ---------------------------------------------------------------------------
# Preset: minimal -- nothing pre-approved
# ---------------------------------------------------------------------------

PRESET_MINIMAL: list[PresetDecision] = []

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PRESETS: dict[str, list[PresetDecision]] = {
    "readonly": PRESET_READONLY,
    "developer": PRESET_DEVELOPER,
    "minimal": PRESET_MINIMAL,
}


def get_preset_names() -> list[str]:
    """Return sorted list of available preset names."""
    return sorted(PRESETS.keys())


def get_preset(name: str) -> list[PresetDecision]:
    """Get a preset by name. Raises KeyError if not found."""
    if name not in PRESETS:
        raise KeyError(f"Unknown preset: '{name}'. Available: {get_preset_names()}")
    return PRESETS[name]


def apply_preset(
    preset_name: str,
    organization_id: str = "default",
    project_id: str = "global",
    num_synthetic_decisions: int | None = None,
) -> int:
    """Apply a bootstrap preset by inserting synthetic permission decisions.

    Each pattern in the preset gets ``num_synthetic_decisions`` PermissionLog
    entries with ``decided_by='human:bootstrap'`` and ``decision=ALLOW``.
    These are immediately visible to the learning engine, so matching
    patterns will auto-approve on the next check.

    Args:
        preset_name: Name of the preset (e.g. "developer", "readonly").
        organization_id: Tenant ID for the decisions.
        num_synthetic_decisions: How many synthetic decisions per pattern.
            Defaults to ``permission_learning_min_decisions + 1``.

    Returns:
        Total number of PermissionLog records inserted.

    Raises:
        KeyError: If preset_name is unknown.
    """
    preset = get_preset(preset_name)

    if not preset:
        return 0

    if num_synthetic_decisions is None:
        num_synthetic_decisions = aiperture.config.settings.permission_learning_min_decisions + 1

    now = datetime.now(UTC).replace(tzinfo=None)
    total = 0

    with Session(get_engine()) as session:
        for pattern in preset:
            for _ in range(num_synthetic_decisions):
                entry = PermissionLog(
                    organization_id=organization_id,
                    project_id=project_id,
                    tool=pattern.tool,
                    action=pattern.action,
                    scope=pattern.scope,
                    decision=PermissionDecision.ALLOW.value,
                    decided_by="human:bootstrap",
                    runtime_id="bootstrap",
                    created_at=now,
                )
                session.add(entry)
                total += 1
        session.commit()

    return total
