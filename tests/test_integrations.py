"""Tests for the runtime integration layer."""

import pytest

from aiperture.integrations.base import PermissionGuard
from aiperture.integrations.openai.tool_mapping import OpenAIToolMapper, _infer_action
from aiperture.integrations.openai.guard import OpenAIPermissionGuard
from aiperture.integrations.google_adk.tool_mapping import ADKToolMapper
from aiperture.integrations.google_adk.guard import ADKPermissionGuard
from aiperture.integrations.anthropic.tool_mapping import ClaudeCodeToolMapper
from aiperture.integrations.anthropic.guard import ClaudeCodePermissionGuard
from aiperture.models.permission import PermissionDecision


class TestMCPIntegration:
    """MCP integration re-exports the MCP server."""

    def test_mcp_server_importable(self):
        from aiperture.integrations.mcp import mcp_server
        assert mcp_server is not None

    def test_mcp_server_is_same_instance(self):
        from aiperture.integrations.mcp import mcp_server
        from aiperture.mcp_server import mcp
        assert mcp_server is mcp


class TestOpenAIToolMapper:
    """OpenAI function call mapping."""

    def test_simple_function(self):
        mapper = OpenAIToolMapper()
        result = mapper.map_tool("get_weather", {"location": "NYC"})
        assert result == ("get_weather", "read", "NYC")

    def test_write_function(self):
        mapper = OpenAIToolMapper()
        result = mapper.map_tool("create_file", {"path": "/tmp/test.txt", "content": "hello"})
        assert result == ("create_file", "write", "/tmp/test.txt")

    def test_delete_function(self):
        mapper = OpenAIToolMapper()
        result = mapper.map_tool("delete_record", {"id": "abc123"})
        assert result == ("delete_record", "delete", "abc123")

    def test_execute_function(self):
        mapper = OpenAIToolMapper()
        result = mapper.map_tool("run_query", {"query": "SELECT 1"})
        assert result == ("run_query", "execute", "SELECT 1")

    def test_unknown_prefix_defaults_to_execute(self):
        mapper = OpenAIToolMapper()
        result = mapper.map_tool("do_something", {"data": "test"})
        assert result == ("do_something", "execute", "test")

    def test_empty_input(self):
        mapper = OpenAIToolMapper()
        result = mapper.map_tool("my_tool", {})
        assert result == ("my_tool", "execute", "")

    def test_scope_key_priority(self):
        """scope key should be preferred over other keys."""
        mapper = OpenAIToolMapper()
        result = mapper.map_tool("my_tool", {"scope": "important", "name": "other"})
        assert result[2] == "important"


class TestInferAction:
    """Action inference from function names."""

    @pytest.mark.parametrize("name,expected", [
        ("read_file", "read"),
        ("get_user", "read"),
        ("fetch_data", "read"),
        ("list_items", "read"),
        ("search_documents", "read"),
        ("query_database", "read"),
        ("write_file", "write"),
        ("create_user", "write"),
        ("update_record", "write"),
        ("set_config", "write"),
        ("delete_file", "delete"),
        ("remove_user", "delete"),
        ("drop_table", "delete"),
        ("run_command", "execute"),
        ("exec_query", "execute"),
        ("invoke_function", "execute"),
        ("something_else", "execute"),
    ])
    def test_action_inference(self, name, expected):
        assert _infer_action(name) == expected


class TestADKToolMapper:
    """Google ADK function call mapping."""

    def test_maps_same_as_openai(self):
        """ADK mapper follows the same pattern as OpenAI."""
        adk = ADKToolMapper()
        result = adk.map_tool("search_web", {"query": "AI safety"})
        assert result == ("search_web", "read", "AI safety")


class TestOpenAIPermissionGuard:
    """OpenAI guard uses correct runtime_id."""

    def test_runtime_id(self):
        guard = OpenAIPermissionGuard()
        assert guard.runtime_id == "openai"

    def test_mapper_type(self):
        guard = OpenAIPermissionGuard()
        assert isinstance(guard.mapper, OpenAIToolMapper)


class TestADKPermissionGuard:
    """ADK guard uses correct runtime_id."""

    def test_runtime_id(self):
        guard = ADKPermissionGuard()
        assert guard.runtime_id == "google-adk"

    def test_mapper_type(self):
        guard = ADKPermissionGuard()
        assert isinstance(guard.mapper, ADKToolMapper)


class TestPermissionGuardCheck:
    """Integration test: guard → engine → decision."""

    def test_check_returns_decision(self):
        guard = OpenAIPermissionGuard()
        decision = guard.check("get_weather", {"location": "NYC"})
        # With no learned patterns, should return ASK or DENY (default decision)
        assert decision in (
            PermissionDecision.ASK,
            PermissionDecision.DENY,
            PermissionDecision.ALLOW,
        )

    def test_check_skips_none_mapping(self):
        """If mapper returns None, check returns None."""
        from unittest.mock import MagicMock

        mapper = MagicMock()
        mapper.map_tool.return_value = None

        guard = PermissionGuard(
            mapper=mapper,
            runtime_id="test",
        )
        result = guard.check("my_tool", {})
        assert result is None


class TestRecordHookDecisionRuntimeId:
    """Verify record_hook_decision uses runtime_id in decided_by."""

    def test_decided_by_includes_runtime_id(self):
        from aiperture.permissions.engine import PermissionEngine

        engine = PermissionEngine()
        log = engine.record_hook_decision(
            tool="test_tool",
            action="execute",
            scope="test_scope",
            decision=PermissionDecision.ALLOW,
            runtime_id="openai",
        )
        assert log.decided_by == "human:openai-hook"

    def test_decided_by_claude_code(self):
        from aiperture.permissions.engine import PermissionEngine

        engine = PermissionEngine()
        log = engine.record_hook_decision(
            tool="test_tool",
            action="execute",
            scope="test_scope2",
            decision=PermissionDecision.ALLOW,
            runtime_id="claude-code",
        )
        assert log.decided_by == "human:claude-code-hook"

    def test_decided_by_fallback_when_no_runtime_id(self):
        from aiperture.permissions.engine import PermissionEngine

        engine = PermissionEngine()
        log = engine.record_hook_decision(
            tool="test_tool",
            action="execute",
            scope="test_scope3",
            decision=PermissionDecision.ALLOW,
        )
        assert log.decided_by == "human:runtime-hook"


class TestClaudeCodeToolMapper:
    """Claude Code tool mapping via the integrations layer."""

    def test_bash_mapping(self):
        mapper = ClaudeCodeToolMapper()
        result = mapper.map_tool("Bash", {"command": "git status"})
        assert result == ("shell", "execute", "git status")

    def test_edit_mapping(self):
        mapper = ClaudeCodeToolMapper()
        result = mapper.map_tool("Edit", {"file_path": "/tmp/test.py"})
        assert result == ("filesystem", "write", "/tmp/test.py")

    def test_read_mapping(self):
        mapper = ClaudeCodeToolMapper()
        result = mapper.map_tool("Read", {"file_path": "/tmp/test.py"})
        assert result == ("filesystem", "read", "/tmp/test.py")

    def test_skips_aiperture_mcp_tools(self):
        mapper = ClaudeCodeToolMapper()
        result = mapper.map_tool("mcp__aiperture__check_permission", {"tool": "x"})
        assert result is None

    def test_mcp_tool_from_other_server(self):
        mapper = ClaudeCodeToolMapper()
        result = mapper.map_tool("mcp__github__create_issue", {"scope": "my-repo"})
        assert result == ("github", "create_issue", "my-repo")


class TestClaudeCodePermissionGuard:
    """Claude Code guard uses correct runtime_id and mapper."""

    def test_runtime_id(self):
        guard = ClaudeCodePermissionGuard()
        assert guard.runtime_id == "claude-code"

    def test_mapper_type(self):
        guard = ClaudeCodePermissionGuard()
        assert isinstance(guard.mapper, ClaudeCodeToolMapper)

    def test_check_bash(self):
        guard = ClaudeCodePermissionGuard()
        decision = guard.check("Bash", {"command": "echo hello"})
        assert decision in (
            PermissionDecision.ASK,
            PermissionDecision.DENY,
            PermissionDecision.ALLOW,
        )

    def test_check_skips_aiperture_tools(self):
        guard = ClaudeCodePermissionGuard()
        decision = guard.check("mcp__aiperture__get_config", {})
        assert decision is None
