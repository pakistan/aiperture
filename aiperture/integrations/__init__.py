"""Runtime integrations for AIperture.

Each submodule provides a tool_mapping and middleware for a specific
AI agent runtime. The core PermissionEngine is runtime-agnostic — these
modules translate runtime-specific tool calls into the universal
(tool, action, scope) triple.
"""
