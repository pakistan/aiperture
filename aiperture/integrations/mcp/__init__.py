"""MCP (Model Context Protocol) integration for AIperture.

Any MCP-native runtime can connect to AIperture as an MCP server.
No custom code needed — just point the runtime's MCP config at
``aiperture mcp-serve``.

Supported runtimes (non-exhaustive):
- **OpenClaw** — via ``openclaw.json`` MCP server config
- **Cursor** — via MCP server settings
- **Windsurf** — via MCP server settings
- **Claude Desktop** — via ``claude mcp add aiperture -- aiperture mcp-serve``

Setup::

    # Start the MCP server (stdio transport)
    aiperture mcp-serve

    # Or add directly to Claude Desktop / Claude Code
    claude mcp add aiperture -- aiperture mcp-serve

OpenClaw example config (``openclaw.json``)::

    {
      "mcpServers": {
        "aiperture": {
          "command": "aiperture",
          "args": ["mcp-serve"],
          "env": {
            "AIPERTURE_DB_PATH": "aiperture.db"
          }
        }
      }
    }

The MCP server exposes 10 read-only/append-only tools. See
``aiperture.mcp_server`` for the full tool list and security rationale.
"""

from aiperture.mcp_server import mcp as mcp_server

__all__ = ["mcp_server"]
