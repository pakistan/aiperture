"""Plugin registry for AIperture open-core architecture.

Extension points allow an external package (e.g. ``aiperture-enterprise``) to
register plugins via the ``aiperture.plugins`` entry-point group.  When no
plugins are installed, every ``get()`` call returns its default — the open-source
behaviour is unchanged.

Entry-point format in the plugin package's ``pyproject.toml``::

    [project.entry-points."aiperture.plugins"]
    session_cache = "aiperture_enterprise.cache:create"
    audit_hook    = "aiperture_enterprise.audit:create"

Each entry point must resolve to a **callable factory** that takes no arguments
and returns an object satisfying the relevant Protocol.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "aiperture.plugins"

_registry: dict[str, Any] = {}


# ── Public API ───────────────────────────────────────────────────────


def load_all() -> None:
    """Discover and instantiate all plugins from entry points.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    if _registry:
        return  # already loaded

    eps = importlib.metadata.entry_points()
    group = eps.select(group=ENTRY_POINT_GROUP) if hasattr(eps, "select") else eps.get(ENTRY_POINT_GROUP, [])

    for ep in group:
        try:
            factory = ep.load()
            instance = factory()
            _registry[ep.name] = instance
            logger.info("Loaded plugin: %s", ep.name)
        except Exception:
            logger.warning("Failed to load plugin %s", ep.name, exc_info=True)


def get(name: str, default: Any = None) -> Any:
    """Return a loaded plugin by name, or *default* if not installed."""
    return _registry.get(name, default)


def is_loaded(name: str) -> bool:
    """Check whether a plugin is loaded."""
    return name in _registry


def reset() -> None:
    """Clear the registry. Used in tests."""
    _registry.clear()


# ── Extension-point Protocols ────────────────────────────────────────


@runtime_checkable
class SessionCacheBackend(Protocol):
    """Drop-in replacement for the in-memory OrderedDict session cache."""

    def get(self, key: tuple) -> Any: ...
    def set(self, key: tuple, value: Any) -> None: ...
    def delete(self, key: tuple) -> None: ...
    def delete_matching(self, predicate: Any) -> int: ...
    def __len__(self) -> int: ...


@runtime_checkable
class AuditHook(Protocol):
    """Called after every audit event is committed."""

    def on_audit_event(self, event: Any) -> None: ...


@runtime_checkable
class HealthChecker(Protocol):
    """Extra health checks surfaced at ``GET /health``."""

    @property
    def name(self) -> str: ...
    def check(self) -> dict: ...


@runtime_checkable
class AuthBackend(Protocol):
    """Custom authentication backend for the HTTP API."""

    async def authenticate(self, request: Any) -> None: ...


@runtime_checkable
class DatabaseEngineFactory(Protocol):
    """Custom database engine creation."""

    def create_engine(self, settings: Any) -> Any: ...


@runtime_checkable
class RiskRuleProvider(Protocol):
    """Inject additional risk classification rules.

    Return a RiskAssessment to override, or ``None`` to fall through.
    """

    def classify(self, tool: str, action: str, scope: str) -> Any | None: ...


@runtime_checkable
class IntelligenceBackend(Protocol):
    """Replace the built-in cross-org intelligence engine."""

    def report_decision(self, tool: str, action: str, scope: str, decision_is_allow: bool) -> None: ...
    def get_global_signal(self, tool: str, action: str, scope: str) -> Any | None: ...


@runtime_checkable
class PermissionLogHook(Protocol):
    """Called after every permission decision is logged."""

    def on_permission_logged(self, log_entry: Any) -> None: ...


@runtime_checkable
class PluginRouter(Protocol):
    """Provides extra FastAPI routers to mount."""

    def get_routers(self) -> list: ...


@runtime_checkable
class PluginMCPTools(Protocol):
    """Provides extra MCP tool registrations."""

    def register_tools(self, mcp: Any) -> None: ...


@runtime_checkable
class PluginConfig(Protocol):
    """Provides additional configuration sections."""

    def get_config_fields(self) -> dict: ...
