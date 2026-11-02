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


class ToolFeedbackError(ExecutionError):
    """An explicit, model-readable rejection of a read-only tool request."""

    def __init__(self, code: str, message: str):
        super().__init__(message[:1000])
        self.code = code[:80]

    def observation(self):
        return {"error": {"code": self.code, "message": str(self)}}


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
    idempotent: bool = False
    recover: Callable | None = None

    def __post_init__(self):
        check_schema(self.input_schema)
        check_schema(self.output_schema)
        if self.timeout_seconds <= 0:
            raise ValueError("tool timeout must be positive")
        if self.side_effect not in {"read_only", "write"}:
            raise ValueError("tool side_effect must be read_only or write")

    def descriptor(self, alias: str) -> dict:
        return {
            "type": "function",
            "function": {
                "name": alias,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    async def invoke(self, arguments: dict, *, operation_id: str | None = None) -> Any:
        if self.side_effect != "read_only" and operation_id is None:
            raise ExecutionError("write tools require a journaled operation ID")
        Draft202012Validator(self.input_schema).validate(arguments)
        kwargs = dict(arguments)
        if self.idempotent:
            if operation_id is None:
                raise ExecutionError("idempotent tools require an operation ID")
            kwargs["idempotency_key"] = operation_id
        async with asyncio.timeout(self.timeout_seconds):
            if inspect.iscoroutinefunction(self.function):
                result = await self.function(**kwargs)
            else:
                result = await asyncio.to_thread(self.function, **kwargs)
        canonical_json(result)
        Draft202012Validator(self.output_schema).validate(result)
        return result


@dataclass(frozen=True)
class ExternalStatus:
    status: str
    output: Any = None
    error: str | None = None

    def __post_init__(self):
        if self.status not in {"pending", "succeeded", "failed", "canceled"}:
            raise ValueError("invalid external job state")


@dataclass(frozen=True)
class ExternalTool:
    """Asynchronous service job; submit must honor the supplied idempotency key."""

    name: str
    description: str
    input_schema: dict
    output_schema: dict
    submit: Callable
    poll: Callable
    cancel: Callable | None = None
    version: str = "1"
    side_effect: str = "write"
    timeout_seconds: float = 30.0
    idempotent: bool = True
    job_timeout_seconds: float = 3600.0

    def __post_init__(self):
        check_schema(self.input_schema)
        check_schema(self.output_schema)
        if not self.idempotent or self.timeout_seconds <= 0 or self.job_timeout_seconds <= 0:
            raise ValueError("external jobs require idempotent submit and a positive timeout")
        if self.side_effect not in {"read_only", "write"}:
            raise ValueError("tool side_effect must be read_only or write")

    def descriptor(self, alias: str) -> dict:
        return {
            "type": "function",
            "function": {
                "name": alias,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool | ExternalTool] = {}
        self.bindings: dict[str, dict] = {}

    def register(self, tool: Tool | ExternalTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def resolve(self, name: str, version: str = "1") -> Tool | ExternalTool:
        if name not in self._tools:
            raise ValueError(f"tool plugin is not installed: {name}")
        tool = self._tools[name]
        if tool.version != version:
            raise ValueError(f"tool version mismatch: {name}")
        return tool
