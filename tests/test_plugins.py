"""Tests for the AIperture plugin registry."""

import logging
from unittest.mock import MagicMock, patch

from aiperture import plugins


class TestPluginRegistry:
    """Core registry operations."""

    def test_get_returns_none_when_no_plugins(self):
        """get() returns None by default when no plugins are loaded."""
        assert plugins.get("session_cache") is None
        assert plugins.get("audit_hook") is None
        assert plugins.get("health_checker") is None
        assert plugins.get("auth_backend") is None
        assert plugins.get("db_engine") is None
        assert plugins.get("risk_rules") is None
        assert plugins.get("intelligence_backend") is None
        assert plugins.get("permission_log_hook") is None
        assert plugins.get("router") is None
        assert plugins.get("mcp_tools") is None

    def test_get_returns_custom_default(self):
        """get() returns the supplied default when plugin is not loaded."""
        sentinel = object()
        assert plugins.get("nonexistent", sentinel) is sentinel

    def test_is_loaded_false_when_no_plugins(self):
        """is_loaded() returns False when no plugins are loaded."""
        assert not plugins.is_loaded("session_cache")
        assert not plugins.is_loaded("audit_hook")

    def test_reset_clears_registry(self):
        """reset() clears all loaded plugins."""
        # Manually inject a plugin
        plugins._registry["test_plugin"] = "test_value"
        assert plugins.is_loaded("test_plugin")

        plugins.reset()
        assert not plugins.is_loaded("test_plugin")
        assert plugins.get("test_plugin") is None

    def test_load_all_with_no_entry_points(self):
        """load_all() succeeds silently when no entry points are registered."""
        plugins.load_all()
        assert plugins.get("session_cache") is None

    def test_load_all_is_idempotent(self):
        """Subsequent calls to load_all() are no-ops."""
        plugins._registry["sentinel"] = True
        plugins.load_all()  # should not clear existing
        assert plugins.is_loaded("sentinel")


class TestPluginLoading:
    """Entry-point based plugin loading."""

    def test_load_all_discovers_and_instantiates_plugin(self):
        """load_all() calls the entry-point factory and stores the result."""
        mock_instance = MagicMock()
        mock_factory = MagicMock(return_value=mock_instance)

        mock_ep = MagicMock()
        mock_ep.name = "test_hook"
        mock_ep.load.return_value = mock_factory

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            plugins.load_all()

        assert plugins.get("test_hook") is mock_instance
        mock_factory.assert_called_once()

    def test_load_all_handles_bad_plugin_gracefully(self, caplog):
        """A plugin that raises during loading is logged and skipped."""
        mock_ep = MagicMock()
        mock_ep.name = "bad_plugin"
        mock_ep.load.side_effect = ImportError("missing dependency")

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            with caplog.at_level(logging.WARNING):
                plugins.load_all()

        assert not plugins.is_loaded("bad_plugin")
        assert "Failed to load plugin bad_plugin" in caplog.text

    def test_load_all_handles_factory_error(self, caplog):
        """A plugin whose factory raises is logged and skipped."""
        mock_factory = MagicMock(side_effect=RuntimeError("init failed"))

        mock_ep = MagicMock()
        mock_ep.name = "broken_plugin"
        mock_ep.load.return_value = mock_factory

        mock_eps = MagicMock()
        mock_eps.select.return_value = [mock_ep]

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            with caplog.at_level(logging.WARNING):
                plugins.load_all()

        assert not plugins.is_loaded("broken_plugin")


class TestProtocols:
    """Protocol classes are runtime-checkable."""

    def test_session_cache_protocol(self):
        """SessionCacheBackend protocol is runtime-checkable."""
        from aiperture.plugins import SessionCacheBackend

        class FakeCache:
            def get(self, key): ...
            def set(self, key, value): ...
            def delete(self, key): ...
            def delete_matching(self, predicate): ...
            def __len__(self): ...

        assert isinstance(FakeCache(), SessionCacheBackend)

    def test_audit_hook_protocol(self):
        """AuditHook protocol is runtime-checkable."""
        from aiperture.plugins import AuditHook

        class FakeHook:
            def on_audit_event(self, event): ...

        assert isinstance(FakeHook(), AuditHook)

    def test_health_checker_protocol(self):
        """HealthChecker protocol is runtime-checkable."""
        from aiperture.plugins import HealthChecker

        class FakeChecker:
            @property
            def name(self): return "test"
            def check(self): ...

        assert isinstance(FakeChecker(), HealthChecker)

    def test_risk_rule_provider_protocol(self):
        """RiskRuleProvider protocol is runtime-checkable."""
        from aiperture.plugins import RiskRuleProvider

        class FakeRules:
            def classify(self, tool, action, scope): ...

        assert isinstance(FakeRules(), RiskRuleProvider)


class TestDefaultSessionCache:
    """Test the _DefaultSessionCache used when no plugin is present."""

    def test_get_set_delete(self):
        """Basic CRUD operations on the default cache."""
        from aiperture.permissions.engine import _DefaultSessionCache

        cache = _DefaultSessionCache(max_size=100)
        key = ("org", "tool", "action", "scope", "session", "hash")

        assert cache.get(key) is None
        cache.set(key, "allow")
        assert cache.get(key) == "allow"
        cache.delete(key)
        assert cache.get(key) is None

    def test_lru_eviction(self):
        """Cache evicts oldest entries when max_size is exceeded."""
        from aiperture.permissions.engine import _DefaultSessionCache

        cache = _DefaultSessionCache(max_size=2)
        k1 = ("org", "t", "a", "s1", "sess", "")
        k2 = ("org", "t", "a", "s2", "sess", "")
        k3 = ("org", "t", "a", "s3", "sess", "")

        cache.set(k1, "v1")
        cache.set(k2, "v2")
        assert len(cache) == 2

        cache.set(k3, "v3")
        assert len(cache) == 2
        assert cache.get(k1) is None  # evicted
        assert cache.get(k2) == "v2"
        assert cache.get(k3) == "v3"

    def test_delete_matching(self):
        """delete_matching removes entries matching a predicate."""
        from aiperture.permissions.engine import _DefaultSessionCache

        cache = _DefaultSessionCache(max_size=100)
        k1 = ("org", "shell", "execute", "ls", "sess", "")
        k2 = ("org", "shell", "execute", "rm -rf /", "sess", "")
        k3 = ("org", "fs", "read", "file.txt", "sess", "")

        cache.set(k1, "allow")
        cache.set(k2, "deny")
        cache.set(k3, "allow")

        removed = cache.delete_matching(lambda k: k[1] == "shell")
        assert removed == 2
        assert cache.get(k1) is None
        assert cache.get(k2) is None
        assert cache.get(k3) == "allow"


class TestPluginConfigRegistration:
    """Test plugin config registration."""

    def test_register_plugin_config(self):
        """register_plugin_config stores config fields."""
        from aiperture.config import get_plugin_configs, register_plugin_config

        register_plugin_config("enterprise", {
            "sso_enabled": {"default": False, "description": "Enable SSO"},
        })

        configs = get_plugin_configs()
        assert "enterprise" in configs
        assert "sso_enabled" in configs["enterprise"]

        # Clean up
        from aiperture.config import _plugin_configs
        _plugin_configs.clear()
