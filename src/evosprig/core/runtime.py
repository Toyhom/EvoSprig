"""Sequential DAG execution with a bounded tool loop and observable events."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable

from jsonschema import Draft202012Validator

from .protocols import BudgetExceeded, ExecutionError, ModelProvider, ModelRequest, ToolRegistry
from .spec import Ref, ResourceRef, canonical_json
from .version import AgentVersion


@dataclass
class RunResult:
    run_id: str
    agent_version: str
    status: str = "running"
    output: dict | None = None
    error: dict | None = None
    events: list[dict] = field(default_factory=list)
    usage: dict = field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "model_calls": 0,
            "unreported_model_calls": 0,
            "steps": 0,
            "cost": None,
            "currency": None,
        }
    )
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class Runtime:
    def __init__(self, models: dict[str, ModelProvider], tools: ToolRegistry | None = None):
        self.models = models
        self.tools = tools or ToolRegistry()

    async def run(
        self,
        version: AgentVersion,
        inputs: dict,
        *,
        run_id: str | None = None,
        cancel: asyncio.Event | None = None,
        on_event: Callable[[dict], None] | None = None,
    ) -> RunResult:
        spec = version.spec
        result = RunResult(run_id or uuid.uuid4().hex, version.version_id)
        started = time.monotonic()
        state = {"input": inputs, "nodes": {}}
        budget = spec.execution

        def emit(kind: str, node_id: str | None = None, **data):
            event = {
                "event_version": "0.1",
                "event_id": f"{result.run_id}:{len(result.events) + 1}",
                "run_id": result.run_id,
                "agent_version": version.version_id,
                "sequence": len(result.events) + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": kind,
                "node_id": node_id,
                "data": data,
            }
            result.events.append(event)
            if on_event:
                on_event(event)

        def check_step():
            if cancel and cancel.is_set():
                raise asyncio.CancelledError
            if result.usage["steps"] >= budget.max_steps:
                raise BudgetExceeded("step budget exhausted")
            result.usage["steps"] += 1

        def resolve(values):
            output = {}
            for key, value in values.items():
                if isinstance(value, Ref):
                    cursor = state
                    for segment in value.ref.split("."):
                        if isinstance(cursor, list) and segment.isdigit():
                            cursor = cursor[int(segment)]
                        else:
                            cursor = cursor[segment]
                    output[key] = cursor
                else:
                    output[key] = value.value
            return output

        bound_tools = {}

        async def call_tool(alias, arguments, node_id, call_id):
            check_step()
            emit("tool.request", node_id, tool=alias, call_id=call_id)
            output = await bound_tools[alias].invoke(arguments)
            emit("tool.result", node_id, tool=alias, call_id=call_id)
            return output

        async def execute():
            Draft202012Validator(spec.input_schema).validate(inputs)
            for alias, binding in spec.tools.items():
                tool = self.tools.resolve(binding.plugin, binding.version)
                if tool.side_effect != "read_only":
                    raise ExecutionError(f"{alias}: write tools require durable execution support")
                bound_tools[alias] = tool
            for node in spec.graph.nodes.values():
                if not node.model:
                    continue
                requirement = spec.models[node.model]
                if requirement.binding not in self.models:
                    raise ExecutionError(f"missing model binding: {requirement.binding}")
                provider = self.models[requirement.binding]
                required = set(requirement.requires) | {"text"}
                if node.tools:
                    required.add("tool_calling")
                if node.response_format == "json":
                    required.add("structured_output")
                if not required <= provider.capabilities:
                    raise ExecutionError(
                        f"missing model capabilities: {sorted(required - provider.capabilities)}"
                    )
            for node_id in spec.topology()[0]:
                check_step()
                node = spec.graph.nodes[node_id]
                emit("node.started", node_id)
                arguments = resolve(node.inputs)
                if node.type == "tool":
                    output = await call_tool(node.tool, arguments, node_id, uuid.uuid4().hex)
                else:
                    provider = self.models[spec.models[node.model].binding]
                    instructions = (
                        version.resources[node.instructions.resource]
                        if isinstance(node.instructions, ResourceRef)
                        else node.instructions
                    )
                    if node.response_format == "json":
                        instructions += (
                            "\nReturn a JSON object matching this JSON Schema: "
                            + canonical_json(node.output_schema)
                        )
                    messages = [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": canonical_json(arguments)},
                    ]
                    while True:
                        check_step()
                        if result.usage["model_calls"] >= budget.max_model_calls:
                            raise BudgetExceeded("model call budget exhausted")
                        used = result.usage["input_tokens"] + result.usage["output_tokens"]
                        descriptors = [bound_tools[alias].descriptor(alias) for alias in node.tools]
                        # Conservative UTF-8 byte estimate plus message/tool overhead; actual usage settles after response.
                        reservation = (
                            len(
                                canonical_json(
                                    {"messages": messages, "tools": descriptors}
                                ).encode()
                            )
                            + 128
                        )
                        allowance = min(
                            budget.max_output_tokens, budget.max_total_tokens - used - reservation
                        )
                        if allowance < 1:
                            raise BudgetExceeded("insufficient token budget for the next request")
                        request = ModelRequest(
                            messages, descriptors, node.response_format == "json", allowance
                        )
                        result.usage["model_calls"] += 1
                        result.usage["unreported_model_calls"] += 1
                        call_id = uuid.uuid4().hex
                        emit(
                            "model.started",
                            node_id,
                            call_id=call_id,
                            model=provider.model_id,
                            temperature=request.temperature,
                            max_output_tokens=allowance,
                            reserved_input_tokens=reservation,
                        )
                        response = await provider.complete(request)
                        result.usage["unreported_model_calls"] -= 1
                        result.usage["input_tokens"] += response.usage.input_tokens
                        result.usage["output_tokens"] += response.usage.output_tokens
                        emit(
                            "model.completed",
                            node_id,
                            call_id=call_id,
                            model=response.model,
                            usage=asdict(response.usage),
                        )
                        if (
                            result.usage["input_tokens"] + result.usage["output_tokens"]
                            > budget.max_total_tokens
                        ):
                            raise BudgetExceeded(
                                "provider usage exceeded the remaining token budget"
                            )
                        if cancel and cancel.is_set():
                            raise asyncio.CancelledError
                        if not response.tool_calls:
                            output = (
                                json.loads(response.text)
                                if node.response_format == "json"
                                else {"text": response.text}
                            )
                            break
                        if node.type != "agent":
                            raise ExecutionError("model node returned unexpected tool calls")
                        ids = [call.id for call in response.tool_calls]
                        if len(ids) != len(set(ids)):
                            raise ExecutionError("duplicate tool call IDs")
                        messages.append(
                            {
                                "role": "assistant",
                                "content": response.text or None,
                                "tool_calls": [
                                    {
                                        "id": call.id,
                                        "type": "function",
                                        "function": {
                                            "name": call.name,
                                            "arguments": canonical_json(call.arguments),
                                        },
                                    }
                                    for call in response.tool_calls
                                ],
                            }
                        )
                        for call in response.tool_calls:
                            if call.name not in node.tools:
                                raise ExecutionError(
                                    "model requested a tool outside the node allowlist"
                                )
                            observation = await call_tool(
                                call.name, call.arguments, node_id, call.id
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call.id,
                                    "content": canonical_json(observation),
                                }
                            )
                Draft202012Validator(node.output_schema).validate(output)
                state["nodes"][node_id] = {"output": output}
                emit("node.completed", node_id)
            output = resolve(spec.graph.output)
            Draft202012Validator(spec.output_schema).validate(output)
            result.output, result.status = output, "succeeded"

        emit("run.started")
        try:
            async with asyncio.timeout(budget.timeout_seconds):
                await execute()
        except asyncio.CancelledError:
            result.status = "canceled"
            result.error = {
                "code": "canceled",
                "message": "run canceled; in-flight provider charges may remain",
            }
        except TimeoutError:
            result.status = "failed"
            result.error = {"code": "timeout", "message": "execution deadline exceeded"}
        except Exception as exc:
            result.status = "failed"
            # Exception strings can contain provider bodies, prompts or tool arguments.
            result.error = {
                "code": getattr(
                    exc,
                    "code",
                    "validation_error"
                    if isinstance(exc, (ValueError, KeyError))
                    else "execution_error",
                ),
                "message": f"{type(exc).__name__}: execution failed; check schemas, bindings and budgets",
            }
        result.duration_seconds = round(time.monotonic() - started, 6)
        emit("run." + result.status, error=result.error, usage=result.usage)
        return result
