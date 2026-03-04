"""Tests for compliance audit tracking (Fix 4).

Validates that report_tool_execution and get_compliance_report
correctly identify checked vs unchecked tool usage.
"""

from aiperture.stores.audit_store import AuditStore


class TestComplianceReport:
    """Compliance gap detection via audit events."""

    def test_fully_compliant_session(self):
        """All executions have prior checks => 100% compliance."""
        audit = AuditStore()

        # Record a permission check
        audit.record(
            event_type="permission.check",
            summary="deny: shell.execute on ls",
            organization_id="comp-org",
            entity_type="permission",
            entity_id="shell.execute.ls",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "shell", "action": "execute", "scope": "ls", "session_id": "s1"},
        )

        # Record the corresponding execution
        audit.record(
            event_type="tool.executed",
            summary="Executed: shell.execute on ls",
            organization_id="comp-org",
            entity_type="tool_execution",
            entity_id="shell.execute.ls",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "shell", "action": "execute", "scope": "ls", "session_id": "s1"},
        )

        from aiperture.mcp_server import _compute_compliance
        report = _compute_compliance("s1", "comp-org")

        assert report["total_executions"] == 1
        assert report["checked_executions"] == 1
        assert report["unchecked_executions"] == 0
        assert report["compliance_ratio"] == 1.0

    def test_unchecked_execution_detected(self):
        """Execution without prior check => compliance gap."""
        audit = AuditStore()

        # Only record an execution — no permission check
        audit.record(
            event_type="tool.executed",
            summary="Executed: shell.execute on rm -rf",
            organization_id="gap-org",
            entity_type="tool_execution",
            entity_id="shell.execute.rm -rf",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "shell", "action": "execute", "scope": "rm -rf", "session_id": "s2"},
        )

        from aiperture.mcp_server import _compute_compliance
        report = _compute_compliance("s2", "gap-org")

        assert report["total_executions"] == 1
        assert report["checked_executions"] == 0
        assert report["unchecked_executions"] == 1
        assert report["compliance_ratio"] == 0.0
        assert len(report["unchecked_details"]) == 1
        assert report["unchecked_details"][0]["tool"] == "shell"

    def test_mixed_compliance(self):
        """Some checked, some unchecked => partial compliance."""
        audit = AuditStore()
        org = "mixed-org"
        sid = "s3"

        # Checked: filesystem.read on src.py
        audit.record(
            event_type="permission.check",
            summary="allow: filesystem.read on src.py",
            organization_id=org,
            entity_type="permission",
            entity_id="filesystem.read.src.py",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "filesystem", "action": "read", "scope": "src.py", "session_id": sid},
        )
        audit.record(
            event_type="tool.executed",
            summary="Executed: filesystem.read on src.py",
            organization_id=org,
            entity_type="tool_execution",
            entity_id="filesystem.read.src.py",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "filesystem", "action": "read", "scope": "src.py", "session_id": sid},
        )

        # Unchecked: shell.execute on curl
        audit.record(
            event_type="tool.executed",
            summary="Executed: shell.execute on curl",
            organization_id=org,
            entity_type="tool_execution",
            entity_id="shell.execute.curl",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "shell", "action": "execute", "scope": "curl", "session_id": sid},
        )

        from aiperture.mcp_server import _compute_compliance
        report = _compute_compliance(sid, org)

        assert report["total_executions"] == 2
        assert report["checked_executions"] == 1
        assert report["unchecked_executions"] == 1
        assert report["compliance_ratio"] == 0.5

    def test_no_executions_full_compliance(self):
        """No executions at all => ratio defaults to 1.0."""
        from aiperture.mcp_server import _compute_compliance
        report = _compute_compliance("empty-session", "empty-org")

        assert report["total_executions"] == 0
        assert report["compliance_ratio"] == 1.0

    def test_session_filter_isolates(self):
        """Compliance report respects session_id filter."""
        audit = AuditStore()
        org = "filter-org"

        # Session A: checked
        audit.record(
            event_type="permission.check",
            summary="check",
            organization_id=org,
            entity_type="permission",
            entity_id="filesystem.read.a",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "filesystem", "action": "read", "scope": "a", "session_id": "sA"},
        )
        audit.record(
            event_type="tool.executed",
            summary="exec",
            organization_id=org,
            entity_type="tool_execution",
            entity_id="filesystem.read.a",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "filesystem", "action": "read", "scope": "a", "session_id": "sA"},
        )

        # Session B: unchecked
        audit.record(
            event_type="tool.executed",
            summary="exec",
            organization_id=org,
            entity_type="tool_execution",
            entity_id="shell.execute.hack",
            actor_type="runtime",
            runtime_id="mcp",
            details={"tool": "shell", "action": "execute", "scope": "hack", "session_id": "sB"},
        )

        from aiperture.mcp_server import _compute_compliance

        # Session A should be fully compliant
        report_a = _compute_compliance("sA", org)
        assert report_a["compliance_ratio"] == 1.0
        assert report_a["unchecked_executions"] == 0

        # Session B should have a gap
        report_b = _compute_compliance("sB", org)
        assert report_b["compliance_ratio"] == 0.0
        assert report_b["unchecked_executions"] == 1


class TestComplianceConfig:
    """Compliance tracking config flag."""

    def test_compliance_settings_exist(self):
        """Core compliance settings exist."""
        import aiperture.config
        # compliance_tracking_enabled was removed (unused dead config)
        assert hasattr(aiperture.config.settings, "permission_learning_enabled")
