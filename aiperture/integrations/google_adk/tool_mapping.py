"""Map Google ADK tool calls to AIperture (tool, action, scope) triples.

Google ADK uses FunctionDeclaration for tools. The mapping follows the
same heuristic as OpenAI — function name + arguments → (tool, action, scope).
"""

from __future__ import annotations

from typing import Any


class ADKToolMapper:
    """Map Google ADK function calls to (tool, action, scope) triples."""

    _SCOPE_KEYS = ("scope", "path", "file_path", "url", "query", "command",
                    "resource", "location", "filename", "name", "id")

    def map_tool(
        self, tool_name: str, tool_input: dict[str, Any],
    ) -> tuple[str, str, str] | None:
        action = _infer_action(tool_name)
        scope = _extract_scope(tool_input)
        return (tool_name, action, scope)


def _infer_action(func_name: str) -> str:
    """Infer an action verb from the function name."""
    name = func_name.lower()

    for prefix in ("read_", "get_", "fetch_", "list_", "search_", "query_"):
        if name.startswith(prefix):
            return "read"

    for prefix in ("write_", "create_", "update_", "set_", "put_", "post_"):
        if name.startswith(prefix):
            return "write"

    for prefix in ("delete_", "remove_", "drop_", "destroy_"):
        if name.startswith(prefix):
            return "delete"

    for prefix in ("run_", "exec_", "execute_", "invoke_", "call_"):
        if name.startswith(prefix):
            return "execute"

    return "execute"


def _extract_scope(params: dict[str, Any]) -> str:
    """Extract the most meaningful scope string from function arguments."""
    for key in ADKToolMapper._SCOPE_KEYS:
        val = params.get(key)
        if val and isinstance(val, str):
            return val

    for val in params.values():
        if isinstance(val, str) and val:
            return val

    return ""
