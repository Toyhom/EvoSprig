"""Deployment bindings are separate from behavior versions."""

import os
from pathlib import Path

import yaml

from evosprig.core.spec import AgentSpec
from evosprig.plugins.mock import MockProvider


def make_models(spec: AgentSpec, profile: str | Path | None = None, mock: bool = False) -> dict:
    bindings = {item.binding for item in spec.models.values()}
    if mock:
        return {name: MockProvider() for name in bindings}
    if not bindings:
        return {}
    from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider

    if profile:
        raw = yaml.safe_load(Path(profile).read_text())
        if not isinstance(raw, dict) or set(raw) - {"models", "tools"} or "models" not in raw:
            raise ValueError("deployment profile needs models and optional tools")
        profiles = raw["models"]
    else:
        profiles = {
            name: {
                "base_url": os.environ.get("EVOSPRIG_BASE_URL", "https://api.deepseek.com"),
                "model": os.environ.get("EVOSPRIG_MODEL", "deepseek-flash"),
                "api_key_env": "DEEPSEEK_API_KEY",
                "options": {"thinking": {"type": "disabled"}},
            }
            for name in bindings
        }
    missing = bindings - profiles.keys()
    if missing:
        raise ValueError(f"missing profile bindings: {sorted(missing)}")
    return {
        name: OpenAICompatibleProvider(Connection.model_validate(profiles[name]))
        for name in bindings
    }


def restore_models(metadata: dict) -> dict:
    """Restore recorded connections; credentials are resolved from the current process environment."""
    models = {}
    for name, binding in metadata.items():
        if binding["adapter"] == "MockProvider":
            models[name] = MockProvider()
        elif binding["adapter"] == "OpenAICompatibleProvider" and "connection" in binding:
            from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider

            models[name] = OpenAICompatibleProvider(
                Connection.model_validate(binding["connection"])
            )
        else:
            raise ValueError("recorded model adapter is unavailable")
    return models


def make_tools(workspace, scope, *, profile=None, bindings=None):
    from evosprig.plugins.builtin_tools import builtin_registry
    from evosprig.plugins.memory_tools import register_memory_tools
    from evosprig.plugins.sqlite_memory import SQLiteMemory

    registry = register_memory_tools(
        builtin_registry(), SQLiteMemory(Path(workspace) / "memory.sqlite"), scope
    )
    if bindings is None:
        raw = yaml.safe_load(Path(profile).read_text()) if profile else {}
        bindings = raw.get("tools", {})
    for name, raw in bindings.items():
        if raw.get("kind") == "http":
            from evosprig.plugins.http_tools import HTTPToolConfig, http_tool

            config = HTTPToolConfig.model_validate(raw)
            tool = http_tool(config)
        elif raw.get("kind") == "external_http":
            from evosprig.plugins.external_http import ExternalHTTPConfig, external_http_tool

            config = ExternalHTTPConfig.model_validate(raw)
            tool = external_http_tool(config)
        elif raw.get("kind") == "mcp":
            from evosprig.plugins.mcp_tools import MCPToolConfig, mcp_tool

            config = MCPToolConfig.model_validate(raw)
            tool = mcp_tool(config)
        else:
            raise ValueError("unknown tool binding kind")
        if name != config.name:
            raise ValueError("tool binding key must match its name")
        registry.register(tool)
        registry.bindings[name] = config.model_dump(mode="json")
    return registry


def load_principals(path):
    from evosprig.server.auth import Principal

    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, list) or not raw:
        raise ValueError("identity configuration must be a nonempty list")
    principals = {}
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"user", "tenant", "token_env"}:
            raise ValueError("each principal needs user, tenant and token_env")
        token = os.environ.get(item["token_env"])
        if not token or token in principals:
            raise ValueError("principal token is empty or duplicated")
        principals[token] = Principal(item["user"], item["tenant"])
    return principals
