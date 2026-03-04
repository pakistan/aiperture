# AIperture Plugin Development Guide

AIperture uses a plugin architecture based on Python entry points. This allows
an external package (e.g. `aiperture-enterprise`) to extend or replace core
behaviours without modifying the open-source codebase.

## How It Works

1. Plugins are discovered via the `aiperture.plugins` entry-point group
2. Each entry point must resolve to a **callable factory** (no arguments)
3. The factory returns an object satisfying the relevant Protocol
4. `plugins.load_all()` is called during startup (API, MCP, CLI)
5. Extension points use `plugins.get("name", default)` — when no plugin is
   installed, the built-in default runs unchanged

## Extension Points

| Name | Protocol | Purpose |
|------|----------|---------|
| `session_cache` | `SessionCacheBackend` | Replace the in-memory session cache (e.g. Redis) |
| `audit_hook` | `AuditHook` | Called after every audit event is committed |
| `health_checker` | `HealthChecker` | Add checks to `GET /health` |
| `auth_backend` | `AuthBackend` | Replace bearer-token auth (e.g. OAuth/OIDC) |
| `db_engine` | `DatabaseEngineFactory` | Replace SQLite/Postgres engine creation |
| `risk_rules` | `RiskRuleProvider` | Inject custom risk classification rules |
| `intelligence_backend` | `IntelligenceBackend` | Replace cross-org DP intelligence |
| `permission_log_hook` | `PermissionLogHook` | Called after every permission decision |
| `router` | `PluginRouter` | Mount extra FastAPI routers |
| `mcp_tools` | `PluginMCPTools` | Register extra MCP tools |

## Example: Enterprise Plugin Package

```
aiperture-enterprise/
├── pyproject.toml
└── aiperture_enterprise/
    ├── __init__.py
    ├── cache.py          # Redis session cache
    ├── audit.py          # Webhook audit hook
    └── auth.py           # OIDC auth backend
```

### pyproject.toml

```toml
[project]
name = "aiperture-enterprise"
dependencies = ["aiperture>=0.2.0"]

[project.entry-points."aiperture.plugins"]
session_cache = "aiperture_enterprise.cache:create"
audit_hook = "aiperture_enterprise.audit:create"
auth_backend = "aiperture_enterprise.auth:create"
```

### aiperture_enterprise/cache.py

```python
import redis

class RedisSessionCache:
    def __init__(self, url: str = "redis://localhost:6379"):
        self._client = redis.from_url(url)

    def get(self, key):
        return self._client.get(str(key))

    def set(self, key, value):
        self._client.set(str(key), value, ex=3600)

    def delete(self, key):
        self._client.delete(str(key))

    def delete_matching(self, predicate):
        # Scan and delete — predicate receives the key tuple
        count = 0
        for k in self._client.scan_iter():
            if predicate(eval(k)):
                self._client.delete(k)
                count += 1
        return count

    def __len__(self):
        return self._client.dbsize()

def create():
    return RedisSessionCache()
```

## Plugin Config

Plugins can register additional config sections:

```python
from aiperture.config import register_plugin_config

def create():
    register_plugin_config("enterprise", {
        "sso_provider": {"default": "", "description": "OIDC provider URL"},
        "redis_url": {"default": "redis://localhost:6379", "description": "Redis URL"},
    })
    return MyPlugin()
```

## Testing

Plugins are automatically reset between tests via the `_reset_plugins` autouse
fixture in `tests/conftest.py`. To test with a mock plugin:

```python
from aiperture import plugins

def test_with_plugin():
    plugins._registry["audit_hook"] = MockAuditHook()
    # ... test code ...
```
