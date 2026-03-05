"""Map OpenAI function calls to AIperture (tool, action, scope) triples.

OpenAI's function calling uses:
  - function name (e.g. "get_weather", "search_documents")
  - arguments dict (e.g. {"location": "NYC", "units": "celsius"})

Since OpenAI function names are user-defined, the mapping is simpler than
Claude Code's — each function name becomes the tool, with "execute" as the
action, and the first meaningful argument as scope.
"""

from __future__ import annotations

from typing import Any


class OpenAIToolMapper:
    """Map OpenAI function calls to (tool, action, scope) triples."""

    # Common argument names that represent a resource scope
    _SCOPE_KEYS = ("scope", "path", "file_path", "url", "query", "command",
                    "resource", "location", "filename", "name", "id")

    def map_tool(
        self, tool_name: str, tool_input: dict[str, Any],
    ) -> tuple[str, str, str] | None:
        """Map an OpenAI function call to (tool, action, scope).

        Heuristics:
        - tool = function name (e.g. "read_file" -> "read_file")
        - action = inferred from function name or defaults to "execute"
        - scope = first meaningful argument value
        """
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
    for key in OpenAIToolMapper._SCOPE_KEYS:
        val = params.get(key)
        if val and isinstance(val, str):
            return val

    # Fall back to first string argument
    for val in params.values():
        if isinstance(val, str) and val:
            return val

    return ""
