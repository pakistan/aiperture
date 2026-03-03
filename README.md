# Aperture

**The permission layer for AI agents.**

AI agents can run shell commands, read your files, call APIs, and modify databases. Today, you're the only thing standing between an agent and `rm -rf /`. Every action gets a yes/no popup. You either approve everything blindly or slow your workflow to a crawl.

Aperture fixes this. It sits between your agent runtime and the outside world, learns your permission preferences over time, and auto-approves the safe stuff — so you only get asked about things that actually matter.

> **Setup guides:** [Claude Code](docs/setup-claude-code.md) | [OpenClaw](docs/setup-openclaw.md) | [REST API](#rest-api) | [Python library](#python-library)

## How it works

```
┌──────────────────────────────────────────────────────────────────┐
│                      Your Agent Runtime                          │
│           (Claude Code, OpenAI Agents, LangChain, etc.)          │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       │  "Can this agent run `npm test`?"
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                         APERTURE                                 │
│                                                                  │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│   │ Permission  │  │ Risk Scoring │  │ Learning Engine       │   │
│   │ Engine      │  │              │  │                       │   │
│   │             │  │ tool danger  │  │ You approved npm test │   │
│   │ RBAC rule   │─▶│ × action     │  │ 15 times in a row.    │   │
│   │ Task grants │  │   severity   │  │ Auto-approving now.   │   │
│   │ Learned     │  │ × scope      │  │                       │   │
│   │   patterns  │  │   breadth    │  │ You denied rm -rf /   │   │
│   │             │  │              │  │ every time.           │   │
│   └──────┬───┬──┘  └──────────────┘  │  Auto-denying now.    │   │
│          │   │                       └-──────────────────────┘   │
│          │   │     ┌──────────────┐  ┌───────────────────────┐   │
│          │   │     │ Audit Trail  │  │ Artifact Store        │   │ 
│          │   └────▶│ Every        │  │ SHA-256 verified      │   │
│          │         │ decision     │  │ immutable storage     │   │
│          │         │ logged       │  │ for agent outputs     │   │
│          │         └──────────────┘  └───────────────────────┘   │
└──────────┼───────────────────────────────────────────────────────┘
           │
           ▼
     ┌─────────────┐
     │  ALLOW      │  ← auto-approved (learned pattern)
     │  DENY       │  ← auto-denied (learned pattern)
     │  ASK        │  ← no pattern yet, ask the human
     └─────────────┘
```

**No LLM calls.** Every decision is deterministic — glob matching, frequency counting, and pattern lookup. Aperture never phones home, never calls an API, and adds zero latency from model inference.

**Runtime agnostic.** Aperture integrates via MCP (for Claude Code, OpenClaw), REST API (for any HTTP-capable runtime), or as a Python library (direct import). MCP is one integration path, not a dependency.

## What you experience

**Day 1** — Run `aperture bootstrap developer` and 75 common safe patterns are auto-approved from the start. You only get asked about things not in the preset. Every decision you make is recorded.

**Day 3** — Aperture has learned your project-specific patterns on top of the bootstrap. Custom build scripts, your test commands, project-specific file paths — all auto-approved. You still get prompted for `rm`, `curl`, and anything touching production.

**Day 7** — The only popups you see are for genuinely new or risky actions. Everything routine is auto-approved. Everything dangerous is auto-denied. Your agent moves faster and you have a full audit trail of every decision.

## Getting started

### 1. Install

```bash
pip install aperture-ai
```

Requires Python 3.12+. This installs the `aperture` CLI and the Python package.

Verify it worked:

```bash
aperture --help
```

You should see:

```
Aperture — The permission layer for AI agents

Commands:
  mcp-serve    Run as MCP server (stdio transport)
  serve        Run HTTP API server
  init-db      Initialize the database
  configure    Interactive setup wizard
  bootstrap    Seed permission decisions from a preset
  revoke       Revoke auto-approval for a permission pattern
```

### 2. Initialize

```bash
aperture init-db
```

This creates `aperture.db` in your current directory (SQLite). That's where all permission decisions, learned patterns, and audit logs are stored.

### 3. Bootstrap safe patterns (recommended)

Skip the cold-start problem where every action is denied:

```bash
aperture bootstrap developer    # 75 pre-approved patterns (git, file reads, test runners, linters)
```

This seeds the learning engine with synthetic decisions for common safe actions — `git status`, `npm test`, reading `.py`/`.ts`/`.json` files, etc. Your agent can do routine work immediately without asking you 75 times first.

Other presets: `readonly` (48 patterns — reads only) or `minimal` (clean slate, learn everything from scratch).

### 4. Connect your agent runtime

Pick whichever runtime you use:

#### Claude Code

Add to your `.mcp.json` (project root or `~/.claude/`):

```json
{
  "mcpServers": {
    "aperture": {
      "type": "stdio",
      "command": "aperture",
      "args": ["mcp-serve"]
    }
  }
}
```

Start Claude Code. It now has 14 Aperture tools — `check_permission`, `approve_action`, `deny_action`, `explain_action`, `get_permission_patterns`, `store_artifact`, `verify_artifact`, `get_cost_summary`, `get_audit_trail`, `get_config`, `report_tool_execution`, `get_compliance_report`, `revoke_permission_pattern`, and `list_auto_approved_patterns`.

**[Full Claude Code guide →](docs/setup-claude-code.md)** — includes learning loop diagram, tuning, and troubleshooting.

#### OpenClaw

```bash
npm install -g openclaw@latest
```

Create `openclaw.json` in your project root:

```json
{
  "mcpServers": {
    "aperture": {
      "command": "aperture",
      "args": ["mcp-serve"],
      "env": {
        "APERTURE_DB_PATH": "./aperture.db"
      }
    }
  }
}
```

Add a [system prompt](examples/system_prompt.md) that tells the agent to call `check_permission` before every action, then run `openclaw chat`.

**[Full OpenClaw guide →](docs/setup-openclaw.md)** — includes step-by-step walkthrough, demo mode, and production settings.

#### REST API

Start the server and point any agent runtime at it:

```bash
aperture serve    # Runs on localhost:8100
```

```bash
# Check a permission
curl -X POST localhost:8100/permissions/check \
  -H "Content-Type: application/json" \
  -d '{"tool": "shell", "action": "execute", "scope": "npm test"}'

# Record a human decision (feeds the learning engine)
curl -X POST localhost:8100/permissions/record \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "shell", "action": "execute", "scope": "npm test",
    "decision": "allow", "decided_by": "user-1"
  }'
```

#### Python library

```python
from aperture.permissions import PermissionEngine
from aperture.models import PermissionDecision

engine = PermissionEngine()

# Check if an action is allowed
verdict = engine.check("shell", "execute", "npm test", rules=[])

# Record a human decision
engine.record_human_decision(
    tool="shell", action="execute", scope="npm test",
    decision=PermissionDecision.ALLOW, decided_by="user-1",
    organization_id="my-org",
)

# After enough decisions, the engine auto-approves
verdict = engine.check("shell", "execute", "npm test", rules=[])
print(verdict.decision)  # PermissionDecision.ALLOW
```

### 5. What to expect

Once connected, here's what your first week looks like:

**First session (with bootstrap)** — Common safe actions are auto-approved immediately. You'll only be prompted for actions outside the preset — writes, installs, network calls, etc. Approve the safe ones; Aperture records your decisions.

**First session (without bootstrap)** — Every action gets checked. You'll approve the safe ones (reading files, running tests, git commands). This is normal — Aperture is building its model of your preferences.

**After ~10 approvals per action** — Aperture starts auto-approving the patterns you've consistently allowed. `git status`? Auto-approved. `npm test`? Auto-approved. You stop seeing prompts for routine actions.

**Dangerous actions stay flagged** — `rm -rf`, `DROP TABLE`, shell commands touching production paths — these are scored as HIGH/CRITICAL risk and always require your explicit approval, no matter how many times you've approved other things.

**You can check what it learned at any time:**

```bash
# Via the API
curl localhost:8100/permissions/patterns?min_decisions=5

# Or ask your agent
"Show me what Aperture has learned"
```

**Optional: tune the learning speed**

The defaults (10 decisions, 95% approval rate) are conservative. To make Aperture learn faster, run the interactive wizard:

```bash
aperture configure
```

Or set environment variables directly:

```bash
export APERTURE_PERMISSION_LEARNING_MIN_DECISIONS=5
export APERTURE_AUTO_APPROVE_THRESHOLD=0.90
```

## How learning works

There's no ML here. No model, no embeddings, no training step. The learning engine is frequency counting with configurable thresholds:

1. Every human decision is recorded as a row: `(tool, action, scope, decision, timestamp, decided_by)`
2. When a new permission check comes in, the engine queries all prior human decisions for that `(tool, action, scope)` tuple
3. It computes the **approval rate** = `allow_count / total_decisions`
4. If `approval_rate >= 0.95` and `total_decisions >= 10` → **auto-approve**
5. If `approval_rate <= 0.05` and `total_decisions >= 10` → **auto-deny**
6. Otherwise → **ask the human again**

Both thresholds are configurable (`APERTURE_AUTO_APPROVE_THRESHOLD`, `APERTURE_PERMISSION_LEARNING_MIN_DECISIONS`).

Two things make this smarter than a flat lookup table:

- **Scope normalization** — `git log --oneline -5` is normalized to `git log*`, so approving any `git log` variant counts toward the same pattern. File paths are normalized similarly: `src/components/Button.tsx` → `src/components/*.tsx`. This means approvals accumulate faster.
- **Exponential decay** — Recent decisions are weighted more heavily (30-day half-life). If you approved something 6 months ago but started denying it last week, the recent denials dominate.

**Safety rails:** Actions scored as HIGH or CRITICAL risk (e.g., `rm -rf`, `DROP TABLE`, `curl | sh`) are **never** auto-approved regardless of history. They always require explicit human approval.

## Why not just use CLAUDE.md rules?

If you use Claude Code, you can already write `CLAUDE.md` rules or use `/permissions` to allowlist specific commands. That works. Aperture is for when it stops working:

| | CLAUDE.md / `/permissions` | Aperture |
|---|---|---|
| **Setup** | You write and maintain rules manually | Learns from your decisions automatically |
| **Scope** | One agent runtime (Claude Code) | Any runtime — Claude Code, OpenAI Agents, LangChain, OpenClaw, custom |
| **Granularity** | Command-level allowlists | Normalizes variants (`git log*`), tracks by content hash, scores risk |
| **Audit** | No record of what was approved or when | Append-only log of every decision with timestamps and who decided |
| **Team use** | Per-developer, not shared | Org-level crowd signals — surfaces what your team usually approves |
| **Revocation** | Delete the rule | `aperture revoke` soft-deletes with audit trail, forces fresh decisions |
| **Verification** | Trust that the agent respects the rules | HMAC challenge-response proves a human saw the verdict |
| **Risk analysis** | None — a rule is a rule | Deep shell analysis (unwraps `bash -c`, pipe-to-exec, `find -exec`) |

If you're a solo developer running Claude Code on personal projects, `CLAUDE.md` rules are probably fine. Aperture is built for teams, for multi-runtime setups, and for anyone who needs an audit trail.

## Features

| Feature | What it does |
|---------|-------------|
| **Permission Engine** | RBAC rules + task-scoped grants (ReBAC) + auto-learning from human decisions |
| **Risk Scoring** | OWASP-inspired `tool danger × action severity × scope breadth` with deep analysis of shell wrappers, pipe-to-exec, and scripting oneliners |
| **Learning Engine** | Frequency-based pattern detection: tracks approval/denial rates per (tool, action, scope) and auto-decides after 10+ consistent decisions |
| **Crowd Wisdom** | Aggregates decisions across your org — surfaces what your team usually approves or denies |
| **Artifact Store** | SHA-256 verified, immutable storage for every agent output |
| **Audit Trail** | Append-only compliance log of every permission decision |
| **Compliance Tracking** | Detects unchecked tool executions — tools that ran without a prior permission check |
| **HMAC Challenge-Response** | Cryptographic proof that a human saw the verdict before approving — prevents agent self-approval |
| **Bootstrap Presets** | Pre-seed safe patterns (`developer`, `readonly`, `minimal`) so Aperture is useful from the first session |
| **Revocation** | Undo learned patterns instantly — `aperture revoke shell execute "rm*"` |
| **Content Awareness** | Differentiates writes to the same file by content hash — a rewrite of `main.py` is flagged even if a prior write was approved |
| **Scope Normalization** | Groups `git log`, `git log --oneline`, `git log -5` into `git log*` so approvals accumulate faster |
| **REST API** | FastAPI server — works with any agent runtime over HTTP |
| **MCP Server** | 14 tools for Claude Code and other MCP-compatible runtimes |
| **CLI** | `aperture serve`, `aperture init-db`, `aperture configure`, `aperture bootstrap`, `aperture revoke` |

## How decisions are made

Aperture resolves permissions in this order, stopping at the first match:

```
1. Session memory     →  Already decided this session? Reuse it.
2. Task grants (ReBAC) →  Scoped permission for this specific task?
3. Learned patterns   →  10+ consistent human decisions? Auto-decide.
4. Static RBAC rules  →  Glob-matched rules (most specific wins).
5. Default deny       →  No match? Deny.
```

When enrichment is enabled, each verdict also includes:
- **Risk assessment** — tier (LOW/MEDIUM/HIGH/CRITICAL), score, factors, reversibility
- **Human-readable explanation** — what the action does, in plain English
- **Crowd signal** — what your org has historically decided for this pattern
- **Similar patterns** — related decisions that might inform this one
- **Recommendation** — auto-approve, auto-deny, suggest a rule, or keep asking

## Security hardening

Aperture includes several layers of protection against agent misuse:

### HMAC challenge-response (anti self-approval)

Every `check_permission` verdict includes a cryptographic challenge token (HMAC-signed with a server-side secret). To approve or deny an action, the caller must echo back the challenge, nonce, and timestamp from the original verdict. This proves a human saw the verdict before acting on it. Agents cannot forge these tokens because they don't have the server secret.

### Deep risk analysis

The risk scorer doesn't just look at the top-level command. It unpacks shell wrappers (`bash -c "rm -rf /"` scores as `rm -rf /`, not `bash`), detects pipe-to-exec patterns (`curl | sh`), scripting oneliners (`python -c "os.system(...)"`), and dangerous `find -exec`/`-delete` commands. HIGH and CRITICAL risk actions are **never** auto-approved regardless of history.

### Compliance audit tracking

Two tools detect when agents bypass permission checks:

- `report_tool_execution` — called after an agent runs a tool, creating an execution record
- `get_compliance_report` — compares executions against prior permission checks, revealing compliance gaps (tools that ran without ever being checked)

### Bootstrap presets

Skip the approval fatigue of the first session:

```bash
aperture bootstrap developer    # 75 safe patterns (git, file reads, test runners, linters)
aperture bootstrap readonly     # 48 patterns (reads only)
aperture bootstrap minimal      # Clean slate
```

### Revocation

Undo any learned pattern instantly:

```bash
aperture revoke shell execute "rm*"              # Revoke all rm-related auto-approvals
aperture revoke filesystem write "*.py" --org=prod  # Org-scoped revocation
```

Revoked decisions are soft-deleted (preserved for audit) but excluded from learning, crowd signals, and auto-approval. The pattern immediately requires fresh human decisions.

### Content awareness

Pass a `content_hash` (SHA-256 of the content being written) with your permission check. Different content gets separate cache entries, so rewriting `main.py` with new content is flagged even if a prior write to `main.py` was approved. The verdict includes a `content_changed` flag when the same file is being written with different content than before.

### Scope normalization

The learning engine normalizes command scopes so that `git log`, `git log --oneline`, and `git log --oneline -5` all count toward the same `git log*` pattern. This means approvals accumulate faster and the system learns from fewer interactions.

<details>
<summary><strong>Configuration</strong></summary>

All settings via environment variables (prefix `APERTURE_`):

| Variable | Default | Description |
|---|---|---|
| `APERTURE_DB_BACKEND` | `sqlite` | `sqlite` or `postgres` |
| `APERTURE_DB_PATH` | `aperture.db` | SQLite file path |
| `APERTURE_POSTGRES_URL` | — | Postgres connection URL |
| `APERTURE_PERMISSION_LEARNING_ENABLED` | `true` | Auto-learn from human decisions |
| `APERTURE_PERMISSION_LEARNING_MIN_DECISIONS` | `10` | Min decisions before auto-deciding |
| `APERTURE_AUTO_APPROVE_THRESHOLD` | `0.95` | Approval rate to trigger auto-approve |
| `APERTURE_AUTO_DENY_THRESHOLD` | `0.05` | Approval rate to trigger auto-deny |
| `APERTURE_INTELLIGENCE_ENABLED` | `false` | Cross-org intelligence (opt-in) |
| `APERTURE_API_HOST` | `0.0.0.0` | API bind host |
| `APERTURE_API_PORT` | `8100` | API bind port |

Or run `aperture configure` for an interactive setup wizard.

</details>

<details>
<summary><strong>Development</strong></summary>

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Requires Python 3.12+.

</details>

## License

Apache 2.0 — see [LICENSE](LICENSE).
