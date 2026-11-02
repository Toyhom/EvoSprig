"""Deployment-owned judge and external evaluator bindings; datasets contain no code."""

from pydantic import Field

from evosprig.core.spec import Contract
from evosprig.plugins.http_tools import HTTPToolConfig, http_tool
from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider

from .environment import EnvironmentConfig
from .industry import IndustryConfig, IndustryEnvironment, industry_score
from .scoring import Assessment


class ScorerConnection(Contract):
    endpoint: str
    auth_env: str | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=600)


class EvaluationConfig(Contract):
    industry: IndustryConfig | None = None
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    judges: dict[str, Connection] = Field(default_factory=dict)
    scorers: dict[str, ScorerConnection] = Field(default_factory=dict)


def evaluation_dependencies(raw=None, *, mock=False):
    config = EvaluationConfig.model_validate(raw or {})
    judges = {
        name: OpenAICompatibleProvider(connection) for name, connection in config.judges.items()
    }
    if mock and judges:
        from evosprig.plugins.mock import MockProvider

        judges = {name: MockProvider() for name in judges}
    scorers = {}
    for name, connection in config.scorers.items():
        tool = http_tool(
            HTTPToolConfig(
                name=name,
                description="Evaluate an application result",
                endpoint=connection.endpoint,
                auth_env=connection.auth_env,
                timeout_seconds=connection.timeout_seconds,
                method="POST",
                input_schema={"type": "object"},
                output_schema=Assessment.model_json_schema(),
            )
        )

        async def call(payload, tool=tool):
            return await tool.invoke(payload)

        scorers[name] = call
    if config.industry is not None:
        if "industry" in scorers:
            raise ValueError("industry scorer is reserved for business-state replay")
        scorers["industry"] = industry_score
    return {
        **({"environment": IndustryEnvironment(config.industry)} if config.industry else {}),
        "judge_models": judges or None,
        "scorers": scorers,
        "environment_config": config.environment,
    }
