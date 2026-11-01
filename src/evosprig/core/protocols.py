"""Provider and tool contracts; no concrete backend imports."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from jsonschema import Draft202012Validator

from .spec import canonical_json, check_schema


class ExecutionError(Exception):
    code = "execution_error"


class BudgetExceeded(ExecutionError):
    code = "budget_exhausted"


class ProviderError(ExecutionError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self):
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("usage must be nonnegative")

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ModelRequest:
    messages: list[dict]
    tools: list[dict] = field(default_factory=list)
    json_output: bool = False
    max_output_tokens: int = 512
    temperature: float = 0.0


@dataclass(frozen=True)
class ModelResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    model: str = "unknown"


class ModelProvider(Protocol):
    capabilities: frozenset[str]
    model_id: str

    async def complete(self, request: ModelRequest) -> ModelResponse: ...


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    function: Callable
    version: str = "1"
    side_effect: str = "read_only"
    timeout_seconds: float = 10.0

    def __post_init__(self):
        check_schema(self.input_schema)
        check_schema(self.output_schema)
        if self.timeout_seconds <= 0:
            raise ValueError("tool timeout must be positive")

    def descriptor(self, alias: str) -> dict:
        return {
            "type": "function",
            "function": {
                "name": alias,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    async def invoke(self, arguments: dict) -> Any:
        if self.side_effect != "read_only":
            raise ExecutionError(
                "M0 supports read-only tools; durable side effects require a later runtime"
            )
        Draft202012Validator(self.input_schema).validate(arguments)
        async with asyncio.timeout(self.timeout_seconds):
            if inspect.iscoroutinefunction(self.function):
                result = await self.function(**arguments)
            else:
                result = await asyncio.to_thread(self.function, **arguments)
        canonical_json(result)
        Draft202012Validator(self.output_schema).validate(result)
        return result


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def resolve(self, name: str, version: str = "1") -> Tool:
        if name not in self._tools:
            raise ValueError(f"tool plugin is not installed: {name}")
        tool = self._tools[name]
        if tool.version != version:
            raise ValueError(f"tool version mismatch: {name}")
        return tool
