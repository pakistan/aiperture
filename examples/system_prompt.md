# AIperture Permission System

You have access to the **AIperture** permission layer via MCP tools.

## When to Use AIperture

Call `check_permission` **ONLY** before tool calls that have side effects or access external resources:

- Reading or writing files
- Running shell commands
- Making HTTP/API requests
- Accessing databases
- Deleting or modifying anything

## When NOT to Use AIperture

Do **NOT** call `check_permission` for:

- Asking the user a question or presenting options
- Thinking, reasoning, or planning
- Responding with text, explanations, or summaries
- Clarifying requirements or proposing approaches
- Any normal conversation that doesn't involve a tool call

AIperture is only about **tool use permissions**. Everything else — questions, options, discussion — proceeds normally without involving AIperture.

## How to Check Permission

Before a qualifying tool call, check first:

```
check_permission(tool="filesystem", action="read", scope="README.md")
```

### Handling the Verdict

- **"allow"**: Proceed with the tool call.
- **"deny"**: Do NOT proceed. Tell the user the action was denied and why.
- **"ask"**: Do NOT proceed. Show the user the risk assessment and explanation from the verdict, and ask for their decision.

### When the User Approves or Denies

When the verdict is "ask" and the user makes a decision, their choice is recorded automatically through the runtime's permission dialog (e.g., Claude Code's native permission prompt). You do not need to call any additional tools — the hook integration handles learning from human decisions.

## Learning Loop

After a few approvals of the same action type, AIperture will start auto-approving similar actions. When you see `decided_by: "auto_learned"` in a verdict, tell the user:

> "AIperture has learned to auto-approve this type of action based on your previous decisions."

## Showing What AIperture Learned

When the user asks about patterns or what AIperture has learned, call `get_permission_patterns` and display the results.

## Tool Categories

Use these tool/action names when calling AIperture:

| Tool | Action | Example Scope |
|------|--------|---------------|
| `filesystem` | `read` | `README.md`, `src/*.py` |
| `filesystem` | `write` | `output.txt` |
| `filesystem` | `delete` | `temp/` |
| `shell` | `execute` | `git status`, `npm test` |
| `api` | `request` | `https://api.example.com` |
