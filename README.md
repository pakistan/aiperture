# Aperture

**The permission layer for AI agents.**

AI agents can run shell commands, read your files, call APIs, and modify databases. Today, you're the only thing standing between an agent and `rm -rf /`. Every action gets a yes/no popup. You either approve everything blindly or slow your workflow to a crawl.

Aperture fixes this. It sits between your agent runtime and the outside world, learns your permission preferences over time, and auto-approves the safe stuff — so you only get asked about things that actually matter.

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
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│   │ Permission   │  │ Risk Scoring │  │ Learning Engine       │  │
│   │ Engine       │  │              │  │                       │  │
│   │              │  │ tool danger  │  │ You approved npm test │  │
│   │ RBAC rules   │─▶│ × action     │  │ 15 times in a row.   │  │
│   │ Task grants  │  │   severity   │  │ Auto-approving now.   │  │
│   │ Learned      │  │ × scope      │  │                       │  │
│   │   patterns   │  │   breadth    │  │ You denied rm -rf /   │  │
│   │              │  │              │  │ every time.            │  │
│   └──────┬───┬──┘  └──────────────┘  │ Auto-denying now.     │  │
│          │   │                        └───────────────────────┘  │
│          │   │     ┌──────────────┐  ┌───────────────────────┐  │
│          │   │     │ Audit Trail  │  │ Artifact Store        │  │
│          │   └────▶│ Every        │  │ SHA-256 verified      │  │
│          │         │ decision     │  │ immutable storage     │  │
│          │         │ logged       │  │ for agent outputs     │  │
│          │         └──────────────┘  └───────────────────────┘  │
└──────────┼───────────────────────────────────────────────────────┘
           │
           ▼
     ┌─────────────┐
     │  ALLOW       │  ← auto-approved (learned pattern)
     │  DENY        │  ← auto-denied (learned pattern)
     │  ASK         │  ← no pattern yet, ask the human
     └─────────────┘
```

**No LLM calls.** Every decision is deterministic — glob matching, statistics, and pattern lookup. Aperture never phones home, never calls an API, and adds zero latency from model inference.

## What you experience

**Day 1** — Aperture asks you about everything, just like today. But it's recording your decisions.

**Day 3** — You've approved `npm test`, `git status`, and `cat README.md` a dozen times each. Aperture stops asking about those. You still get prompted for `rm`, `curl`, and anything touching production.

**Day 7** — The only popups you see are for genuinely new or risky actions. Everything routine is auto-approved. Everything dangerous is auto-denied. Your agent moves faster and you have a full audit trail of every decision.

## Quick start

```bash
pip install -e ".[dev]"       # Install
aperture init-db              # Initialize the database
aperture serve                # Start the API server on localhost:8100
```

That's it. Aperture is running. Now connect your agent runtime.

## Connect your runtime

### Claude Code (MCP)

Add to your `.mcp.json`:

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

This gives Claude Code 9 tools: `check_permission`, `approve_action`, `deny_action`, `explain_action`, `get_permission_patterns`, `store_artifact`, `verify_artifact`, `get_cost_summary`, and `get_audit_trail`.

### REST API

Any agent runtime can use the HTTP API:

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

### OpenClaw

[OpenClaw](https://github.com/ClawDBot/openclaw) is an open-source AI agent runtime. Here's how to wire Aperture as its permission layer:

**1. Install both tools**

```bash
npm install -g openclaw@latest      # OpenClaw
pip install -e ".[dev]"             # Aperture
```

**2. Initialize Aperture**

```bash
aperture init-db
```

**3. Add Aperture to your OpenClaw config**

Create `openclaw.json` in your project root:

```json
{
  "mcpServers": {
    "aperture": {
      "command": "aperture",
      "args": ["mcp-serve"],
      "env": {
        "APERTURE_DB_PATH": "./aperture.db",
        "APERTURE_PERMISSION_LEARNING_MIN_DECISIONS": "3",
        "APERTURE_AUTO_APPROVE_THRESHOLD": "0.80"
      }
    }
  }
}
```

The low thresholds (`3` decisions, `0.80` approval rate) let you see the learning loop quickly. For production, use the defaults (`10` decisions, `0.95` threshold).

**4. Add the system prompt**

Create `system_prompt.md` in the same directory. This tells OpenClaw how to use Aperture's MCP tools:

```markdown
Before using any tool (reading files, running commands, making API calls),
call `check_permission` first:

  check_permission(tool="filesystem", action="read", scope="README.md")

- **"allow"**: Proceed with the action.
- **"deny"**: Do NOT proceed. Ask the user if they want to approve it.
- **"ask"**: Do NOT proceed. Show the user the risk assessment and ask for approval.

When the user approves, call `approve_action`. When they deny, call `deny_action`.
After a few consistent approvals, Aperture auto-approves similar actions.
```

See [`examples/system_prompt.md`](examples/system_prompt.md) for the full version.

**5. Start chatting**

```bash
openclaw chat
```

**What happens:**

```
You:    "Read the file README.md"
Agent:  → calls check_permission(tool="filesystem", action="read", scope="README.md")
        ← DENY (no history)
Agent:  "This action was denied. Want to approve it?"
You:    "Yes"
Agent:  → calls approve_action(...)

... repeat 2 more times ...

You:    "Read setup.py"
Agent:  → calls check_permission(tool="filesystem", action="read", scope="setup.py")
        ← ALLOW (auto_learned)
Agent:  "Aperture auto-approved this — it learned from your previous decisions."
```

**Quick demo (no OpenClaw needed)**

To see the learning loop without installing OpenClaw:

```bash
python examples/openclaw_demo.py --sim
```

This runs the full deny → approve → auto-approve cycle using Aperture's API directly.

### Python library

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

## Features

| Feature | What it does |
|---------|-------------|
| **Permission Engine** | RBAC rules + task-scoped grants (ReBAC) + auto-learning from human decisions |
| **Risk Scoring** | OWASP-inspired `tool danger × action severity × scope breadth` — flags `rm -rf /` as CRITICAL, `cat README.md` as LOW |
| **Learning Engine** | Tracks your approval/denial history per (tool, action, scope). After 10+ consistent decisions, auto-decides |
| **Crowd Wisdom** | Aggregates decisions across your org — surfaces what your team usually approves or denies |
| **Artifact Store** | SHA-256 verified, immutable storage for every agent output |
| **Audit Trail** | Append-only compliance log of every permission decision |
| **MCP Server** | 9 tools for Claude Code via Model Context Protocol |
| **REST API** | FastAPI server for any agent runtime |
| **CLI** | `aperture serve`, `aperture init-db`, `aperture configure` |

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
