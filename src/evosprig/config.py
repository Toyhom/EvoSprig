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
        if not isinstance(raw, dict) or set(raw) != {"models"}:
            raise ValueError("deployment profile must contain only models")
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
