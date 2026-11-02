"""Checkpointed graph execution with fenced tool intents and resumable control flow."""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import time
import uuid
from dataclasses import asdict

from jsonschema import Draft202012Validator

from .expressions import predicate, resolve_inputs
from .journal import TERMINAL, LeaseLost, MemoryJournal, Scope, check_lease
from .protocols import BudgetExceeded, ExecutionError, ExternalStatus, ExternalTool, ModelRequest
from .spec import ResourceRef, canonical_json, digest
from .version import AgentVersion


class Suspended(Exception):
    def __init__(self, status: str):
        self.status = status


async def invoke(function, *args, **kwargs):
    if inspect.iscoroutinefunction(function):
        return await function(*args, **kwargs)
    return await asyncio.to_thread(function, *args, **kwargs)


class Engine:
    def __init__(self, models, tools, journal=None, *, allow_writes=False, lease_seconds=30.0):
        self.models, self.tools = models, tools
        self.journal = journal if journal is not None else MemoryJournal()
        self.allow_writes = allow_writes
        self.lease_seconds = lease_seconds

    def model_metadata(self):
        result = {}
        for name, provider in self.models.items():
            result[name] = {"model": provider.model_id, "adapter": type(provider).__qualname__}
            connection = getattr(provider, "connection", None)
            if connection is not None:
                result[name]["connection"] = connection.model_dump(mode="json")
        return result

    def create_run(self, version, inputs, *, run_id=None, scope=None):
        run_id = run_id or uuid.uuid4().hex
        scope = scope or Scope(version.spec.id)
        self.journal.create(
            run_id,
            version,
            inputs,
            scope,
            {
                "models": self.model_metadata(),
                "tools": self.tools.bindings,
                "allow_writes": self.allow_writes,
            },
        )
        return run_id

    async def run(
        self, version, inputs, *, run_id=None, scope=None, cancel=None, on_event=None, shutdown=None
    ):
        run_id = self.create_run(version, inputs, run_id=run_id, scope=scope)
        return await self.resume(
            run_id, scope=scope, cancel=cancel, on_event=on_event, shutdown=shutdown
        )

    def result(self, run_id, scope=None):
        from .runtime import RunResult

        record = self.journal.get(run_id, scope)
        checkpoint = record["checkpoint"]
        return RunResult(
            run_id,
            record["version"]["version_id"],
            record["status"],
            checkpoint["output"],
            checkpoint["error"],
            self.journal.events(run_id),
            checkpoint["usage"],
            checkpoint["active_seconds"],
            checkpoint["waiting"],
        )

    async def resume(self, run_id, *, scope=None, cancel=None, on_event=None, shutdown=None):
        record = self.journal.get(run_id, scope)
        if record["status"] in TERMINAL or (
            record["status"] == "waiting_input" and not record["cancel_requested"]
        ):
            return self.result(run_id, scope)
        if record["metadata"]["models"] != self.model_metadata():
            raise ExecutionError("resume requires the original model bindings")
        if record["metadata"].get("tools", {}) != self.tools.bindings:
            raise ExecutionError("resume requires the original tool bindings")
        if record["metadata"]["allow_writes"] != self.allow_writes:
            raise ExecutionError("resume requires the original write permission")
        lease = self.journal.claim(run_id, uuid.uuid4().hex, self.lease_seconds)
        session = ExecutionSession(self, record, lease, cancel, on_event)
        parent = asyncio.current_task()
        lost = None

        async def watch():
            nonlocal lost
            while True:
                await asyncio.sleep(min(self.lease_seconds / 3, 0.5))
                try:
                    self.journal.heartbeat(lease, self.lease_seconds)
                    if (
                        (shutdown and shutdown.is_set())
                        or (cancel and cancel.is_set())
                        or self.journal.get(run_id)["cancel_requested"]
                    ):
                        parent.cancel()
                        return
                except LeaseLost as exc:
                    lost = exc
                    parent.cancel()
                    return

        watcher = asyncio.create_task(watch())
        try:
            session.check()
            if not session.cp["started"]:
                session.cp["started"] = True
                session.save("run.started")
            else:
                session.save("run.resumed")
            session.preflight()
            remaining = session.spec.execution.timeout_seconds - session.cp["active_seconds"]
            if remaining <= 0:
                raise TimeoutError
            async with asyncio.timeout(remaining):
                output = await session.graph(session.spec.graph, record["input"], "graph")
                Draft202012Validator(session.spec.output_schema).validate(output)
                session.cp["output"] = output
                session.finish("succeeded")
        except Suspended as exc:
            session.finish(exc.status, delay=1.0 if exc.status == "waiting_external" else 0)
        except asyncio.CancelledError:
            if lost:
                raise lost
            if shutdown and shutdown.is_set() and not self.journal.get(run_id)["cancel_requested"]:
                session.cp["error"] = {
                    "code": "worker_shutdown",
                    "message": "checkpoint saved for the next worker",
                }
                session.finish("queued")
            else:
                await session.cancel_external()
                session.cp["error"] = {
                    "code": "canceled",
                    "message": "run canceled; remote operations are reconciled separately",
                }
                session.finish("canceled")
        except LeaseLost:
            raise
        except TimeoutError:
            await session.cancel_external()
            session.cp["error"] = {
                "code": "timeout",
                "message": "active execution deadline exceeded",
            }
            session.finish("failed")
        except Exception as exc:
            await session.cancel_external()
            session.cp["error"] = {
                "code": getattr(
                    exc,
                    "code",
                    "validation_error" if isinstance(exc, ValueError) else "execution_error",
                ),
                "message": f"{type(exc).__name__}: execution failed; inspect node events and configuration",
            }
            session.finish("failed")
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        return self.result(run_id, scope)


class ExecutionSession:
    def __init__(self, engine, record, lease, cancel, on_event):
        self.engine, self.journal = engine, engine.journal
        self.lease, self.cancel, self.on_event = lease, cancel, on_event
        self.version = AgentVersion(**record["version"])
        self.spec = self.version.spec
        self.cp = record["checkpoint"]
        self.cp["waiting"] = []
        self.cp["error"] = None
        self.started = time.monotonic()
        self.previous_active = self.cp["active_seconds"]
        self.bound_tools = {}
        self.halted = None
        self.tool_slots = asyncio.Semaphore(self.spec.execution.max_parallel_tools)
        self.model_slots = asyncio.Semaphore(self.spec.execution.max_parallel_nodes)

    def save(self, kind=None, path=None, *, status="running", release=False, delay=0, **data):
        self.cp["active_seconds"] = self.previous_active + time.monotonic() - self.started
        events = [{"type": kind, "node_id": path, "data": data}] if kind else []
        added = self.journal.save(self.lease, self.cp, status, events, release=release, delay=delay)
        if self.on_event:
            for event in added:
                self.on_event(event)

    def finish(self, status, delay=0):
        self.save(
            "run." + status,
            status=status,
            release=True,
            delay=delay,
            error=self.cp["error"],
            usage=self.cp["usage"],
        )

    def check(self, step=False):
        if self.halted:
            raise self.halted
        record = self.journal.get(self.lease.run_id)
        check_lease(record, self.lease)
        if (self.cancel and self.cancel.is_set()) or record["cancel_requested"]:
            raise asyncio.CancelledError
        if step:
            if self.cp["usage"]["steps"] >= self.spec.execution.max_steps:
                raise BudgetExceeded("step budget exhausted")
            self.cp["usage"]["steps"] += 1

    def preflight(self):
        Draft202012Validator(self.spec.input_schema).validate(
            self.journal.get(self.lease.run_id)["input"]
        )
        for alias, binding in self.spec.tools.items():
            tool = self.engine.tools.resolve(binding.plugin, binding.version)
            if tool.side_effect != "read_only" and not (
                self.journal.durable
                and self.engine.allow_writes
                and self.spec.execution.allow_side_effects
            ):
                raise ExecutionError(
                    "write tools require durable storage and explicit run/spec permission"
                )
            self.bound_tools[alias] = tool

        def inspect_graph(graph):
            for node in graph.nodes.values():
                if node.model:
                    requirement = self.spec.models[node.model]
                    provider = self.engine.models.get(requirement.binding)
                    required = set(requirement.requires) | {"text"}
                    if node.tools:
                        required.add("tool_calling")
                    if node.response_format == "json":
                        required.add("structured_output")
                    if provider is None or not required <= provider.capabilities:
                        raise ExecutionError("model binding lacks required capabilities")
                if node.body:
                    inspect_graph(node.body)
                for branch in node.branches.values():
                    inspect_graph(branch)

        inspect_graph(self.spec.graph)

    def context(self, graph, inputs, prefix):
        return {
            "input": inputs,
            "nodes": {
                name: {"output": self.cp["nodes"][prefix + "/" + name]["output"]}
                for name in graph.nodes
                if self.cp["nodes"].get(prefix + "/" + name, {}).get("status") == "succeeded"
            },
        }

    def suspend(self, path, status, kind, **details):
        self.cp["waiting"] = [item for item in self.cp["waiting"] if item["path"] != path]
        self.cp["waiting"].append({"path": path, "kind": kind, **details})
        raise Suspended(status)

    async def graph(self, graph, inputs, prefix):
        attempted = set()
        order = self.spec.topology(graph)[0]
        while True:
            self.check()
            pending = [
                name
                for name in order
                if self.cp["nodes"].get(prefix + "/" + name, {}).get("status")
                not in {"succeeded", "skipped"}
            ]
            if not pending:
                return resolve_inputs(graph.output, self.context(graph, inputs, prefix))
            ready = []
            for name in pending:
                path = prefix + "/" + name
                if path in attempted:
                    continue
                incoming = [edge for edge in graph.edges if edge.target == name]
                parents = [
                    self.cp["nodes"].get(prefix + "/" + edge.source, {}) for edge in incoming
                ]
                if any(parent.get("status") not in {"succeeded", "skipped"} for parent in parents):
                    continue
                active = [
                    parent.get("status") == "succeeded"
                    and (edge.when is None or parent.get("output", {}).get("value") is edge.when)
                    for edge, parent in zip(incoming, parents)
                ]
                selected_join = (
                    graph.nodes[name].type == "join" and graph.nodes[name].join == "selected"
                )
                enabled = not incoming or (any(active) if selected_join else all(active))
                if not enabled:
                    self.cp["nodes"][path] = {"status": "skipped"}
                    self.save("node.skipped", path)
                else:
                    ready.append(name)
            if not ready:
                if any(
                    self.cp["nodes"].get(prefix + "/" + name, {}).get("status") == "skipped"
                    for name in pending
                ):
                    continue
                if self.cp["waiting"]:
                    status = (
                        "waiting_input"
                        if any(
                            item["kind"] in {"human", "operation_unknown"}
                            for item in self.cp["waiting"]
                        )
                        else "waiting_external"
                    )
                    raise Suspended(status)
                raise ExecutionError("graph has no runnable node")
            ready = ready[: self.spec.execution.max_parallel_nodes]
            results = await asyncio.gather(
                *(self.node(name, graph.nodes[name], inputs, prefix, graph) for name in ready),
                return_exceptions=True,
            )
            for name, result in zip(ready, results):
                if isinstance(result, Suspended):
                    attempted.add(prefix + "/" + name)
                elif isinstance(result, BaseException):
                    raise result

    async def node(self, name, node, inputs, prefix, graph):
        path = prefix + "/" + name
        slot = self.cp["nodes"].setdefault(path, {"status": "new"})
        try:
            self.check()
            if slot["status"] == "new":
                self.check(step=True)
                slot["status"] = "running"
                self.save("node.started", path)
            else:
                slot["status"] = "running"
            context = self.context(graph, inputs, prefix)
            arguments = resolve_inputs(node.inputs, context)
            if node.type in {"transform", "join"}:
                output = arguments
            elif node.type == "condition":
                output = {"value": predicate(node.condition, context)}
            elif node.type == "human":
                if path not in self.cp["responses"]:
                    self.suspend(
                        path, "waiting_input", "human", input=arguments, schema=node.output_schema
                    )
                output = self.cp["responses"][path]
            elif node.type == "loop":
                output = arguments
                for iteration in range(node.max_iterations):
                    output = await self.graph(node.body, output, f"{path}/iteration-{iteration}")
                    if node.until and predicate(node.until, {"input": output}):
                        break
            elif node.type == "parallel":
                semaphore = asyncio.Semaphore(self.spec.execution.max_parallel_nodes)

                async def branch(branch_name, body):
                    async with semaphore:
                        return await self.graph(body, arguments, path + "/" + branch_name)

                names = sorted(node.branches)
                values = await asyncio.gather(
                    *(branch(key, node.branches[key]) for key in names), return_exceptions=True
                )
                errors = [value for value in values if isinstance(value, BaseException)]
                if errors:
                    fatal = next(
                        (error for error in errors if not isinstance(error, Suspended)), errors[0]
                    )
                    raise fatal
                output = dict(zip(names, values))
            elif node.type == "tool":
                output = await self.tool(node.tool, arguments, path, "direct")
            else:
                output = await self.model(node, arguments, path, slot)
            Draft202012Validator(node.output_schema).validate(output)
            slot.update(status="succeeded", output=output)
            self.save("node.completed", path)
            return output
        except Suspended as exc:
            slot["status"] = exc.status
            self.save("node." + exc.status, path)
            raise
        except BaseException as exc:
            if self.halted is None:
                self.halted = exc
            raise

    async def model(self, node, arguments, path, slot):
        provider = self.engine.models[self.spec.models[node.model].binding]
        if "messages" not in slot:
            instructions = (
                self.version.resources[node.instructions.resource]
                if isinstance(node.instructions, ResourceRef)
                else node.instructions
            )
            if node.response_format == "json":
                instructions += (
                    "\nReturn a JSON object matching this JSON Schema: "
                    + canonical_json(node.output_schema)
                )
            slot["messages"] = [
                {"role": "system", "content": instructions},
                {"role": "user", "content": canonical_json(arguments)},
            ]
        while True:
            if slot.get("response") is None:
                async with self.model_slots:
                    self.check(step=True)
                    usage, budget = self.cp["usage"], self.spec.execution
                    if usage["model_calls"] >= budget.max_model_calls:
                        raise BudgetExceeded("model call budget exhausted")
                    descriptors = [
                        self.bound_tools[alias].descriptor(alias) for alias in node.tools
                    ]
                    estimate = (
                        len(
                            canonical_json(
                                {"messages": slot["messages"], "tools": descriptors}
                            ).encode()
                        )
                        + 128
                    )
                    remaining = (
                        budget.max_total_tokens
                        - usage["input_tokens"]
                        - usage["output_tokens"]
                        - usage["reserved_tokens"]
                    )
                    allowance = min(budget.max_output_tokens, remaining - estimate)
                    if allowance < 1:
                        raise BudgetExceeded("token budget cannot reserve another request")
                    reservation = estimate + allowance
                    usage["model_calls"] += 1
                    usage["unreported_model_calls"] += 1
                    usage["reserved_tokens"] += reservation
                    call_id = uuid.uuid4().hex
                    self.save(
                        "model.started",
                        path,
                        call_id=call_id,
                        model=provider.model_id,
                        temperature=0.0,
                        max_output_tokens=allowance,
                        reserved_tokens=reservation,
                    )
                    response = await provider.complete(
                        ModelRequest(
                            copy.deepcopy(slot["messages"]),
                            descriptors,
                            node.response_format == "json",
                            allowance,
                        )
                    )
                    usage["input_tokens"] += response.usage.input_tokens
                    usage["output_tokens"] += response.usage.output_tokens
                    usage["reserved_tokens"] -= reservation
                    usage["unreported_model_calls"] -= 1
                    slot["response"] = asdict(response)
                    slot["turn"] = slot.get("turn", 0) + 1
                    slot["tool_index"] = 0
                    self.save(
                        "model.completed",
                        path,
                        call_id=call_id,
                        model=response.model,
                        usage=asdict(response.usage),
                    )
                    if (
                        usage["input_tokens"] + usage["output_tokens"] + usage["reserved_tokens"]
                        > budget.max_total_tokens
                    ):
                        raise BudgetExceeded("provider usage exceeded reserved budget")
            self.check()
            response = slot["response"]
            calls = response["tool_calls"]
            if not calls:
                return (
                    json.loads(response["text"])
                    if node.response_format == "json"
                    else {"text": response["text"]}
                )
            if node.type != "agent" or len({call["id"] for call in calls}) != len(calls):
                raise ExecutionError("unexpected or duplicate tool calls")
            if not slot.get("assistant_recorded"):
                slot["messages"].append(
                    {
                        "role": "assistant",
                        "content": response["text"] or None,
                        "tool_calls": [
                            {
                                "id": call["id"],
                                "type": "function",
                                "function": {
                                    "name": call["name"],
                                    "arguments": canonical_json(call["arguments"]),
                                },
                            }
                            for call in calls
                        ],
                    }
                )
                slot["assistant_recorded"] = True
                self.save()
            while slot["tool_index"] < len(calls):
                call = calls[slot["tool_index"]]
                if call["name"] not in node.tools:
                    raise ExecutionError("tool call is outside this node's allowlist")
                output = await self.tool(
                    call["name"],
                    call["arguments"],
                    path,
                    call["id"],
                    operation_key=f"model-{slot['turn']}:{call['id']}",
                )
                slot["messages"].append(
                    {"role": "tool", "tool_call_id": call["id"], "content": canonical_json(output)}
                )
                slot["tool_index"] += 1
                self.save()
            slot["response"] = None
            slot["assistant_recorded"] = False
            self.save()

    async def tool(self, alias, arguments, path, call_id, operation_key=None):
        self.check()
        tool = self.bound_tools[alias]
        Draft202012Validator(tool.input_schema).validate(arguments)
        operation_id = digest([self.lease.run_id, path, operation_key or call_id])
        operation = self.journal.operation(self.lease, operation_id)
        fresh = operation is None
        if fresh:
            self.check(step=True)
            operation = self.journal.operation(
                self.lease,
                operation_id,
                {
                    "alias": alias,
                    "path": path,
                    "call_id": call_id,
                    "arguments": arguments,
                    "side_effect": tool.side_effect,
                    "created_at": time.time(),
                },
            )
            self.save("tool.request", path, tool=alias, call_id=call_id, operation_id=operation_id)
        if operation["intent"]["arguments"] != arguments or operation["intent"]["alias"] != alias:
            raise ExecutionError("operation identity does not match its original intent")
        if operation["status"] == "succeeded":
            return operation["output"]
        response_path = path + "/operation-" + operation_id
        if response_path in self.cp["responses"]:
            output = self.cp["responses"][response_path]
            Draft202012Validator(tool.output_schema).validate(output)
            self.journal.operation(
                self.lease,
                operation_id,
                update={"status": "succeeded", "output": output, "source": "human_reconciliation"},
            )
            self.save("tool.reconciled", path, operation_id=operation_id)
            return output
        if isinstance(tool, ExternalTool):
            if time.time() - operation["intent"]["created_at"] > tool.job_timeout_seconds:
                raise TimeoutError("external job deadline exceeded")
            if "job_id" not in operation:
                if not fresh:
                    self.check(step=True)
                    self.save("external.submit_retry", path, operation_id=operation_id)
                try:
                    async with self.tool_slots, asyncio.timeout(tool.timeout_seconds):
                        self.check()
                        job_id = await invoke(
                            tool.submit, **arguments, idempotency_key=operation_id
                        )
                except (TimeoutError, OSError):
                    self.journal.operation(
                        self.lease, operation_id, update={"status": "submission_unknown"}
                    )
                    self.suspend(
                        response_path,
                        "waiting_external",
                        "external",
                        operation_id=operation_id,
                        tool=alias,
                        state="submission_unknown",
                    )
                if not isinstance(job_id, str) or not job_id or len(job_id) > 512:
                    raise ExecutionError("external tool must return a bounded job ID")
                operation = self.journal.operation(
                    self.lease, operation_id, update={"status": "pending", "job_id": job_id}
                )
                self.save(
                    "external.submitted", path, tool=alias, operation_id=operation_id, job_id=job_id
                )
            try:
                async with self.tool_slots, asyncio.timeout(tool.timeout_seconds):
                    self.check()
                    remote = await invoke(tool.poll, operation["job_id"])
            except (TimeoutError, OSError):
                self.suspend(
                    response_path,
                    "waiting_external",
                    "external",
                    operation_id=operation_id,
                    job_id=operation["job_id"],
                    tool=alias,
                    state="poll_unavailable",
                )
            if not isinstance(remote, ExternalStatus):
                raise ExecutionError("external poll must return ExternalStatus")
            if remote.status == "pending":
                self.suspend(
                    response_path,
                    "waiting_external",
                    "external",
                    operation_id=operation_id,
                    job_id=operation["job_id"],
                    tool=alias,
                )
            if remote.status != "succeeded":
                self.journal.operation(self.lease, operation_id, update={"status": remote.status})
                raise ExecutionError("external task did not succeed")
            output = remote.output
        else:
            if not fresh and tool.side_effect != "read_only" and not tool.idempotent:
                output = None
                if tool.recover:
                    async with asyncio.timeout(tool.timeout_seconds):
                        recovered = await invoke(tool.recover, operation_id)
                    if isinstance(recovered, ExternalStatus) and recovered.status == "succeeded":
                        output = recovered.output
                if output is None:
                    self.suspend(
                        response_path,
                        "waiting_input",
                        "operation_unknown",
                        operation_id=operation_id,
                        tool=alias,
                        schema=tool.output_schema,
                    )
            else:
                try:
                    async with self.tool_slots:
                        self.check()
                        output = await tool.invoke(arguments, operation_id=operation_id)
                except asyncio.CancelledError:
                    if tool.side_effect != "read_only":
                        self.journal.operation(
                            self.lease, operation_id, update={"status": "unknown"}
                        )
                        self.cp["waiting"].append(
                            {
                                "path": response_path,
                                "kind": "operation_unknown",
                                "operation_id": operation_id,
                                "tool": alias,
                                "schema": tool.output_schema,
                            }
                        )
                    raise
                except Exception:
                    if tool.side_effect != "read_only":
                        self.journal.operation(
                            self.lease, operation_id, update={"status": "unknown"}
                        )
                        self.suspend(
                            response_path,
                            "waiting_input",
                            "operation_unknown",
                            operation_id=operation_id,
                            tool=alias,
                            schema=tool.output_schema,
                        )
                    raise
        canonical_json(output)
        Draft202012Validator(tool.output_schema).validate(output)
        self.journal.operation(
            self.lease, operation_id, update={"status": "succeeded", "output": output}
        )
        self.save("tool.result", path, tool=alias, call_id=call_id, operation_id=operation_id)
        return output

    async def cancel_external(self):
        for path, slot in self.cp["nodes"].items():
            node_calls = [("direct", None)]
            if slot.get("response"):
                node_calls = [
                    (f"model-{slot['turn']}:{call['id']}", call["name"])
                    for call in slot["response"]["tool_calls"]
                ]
            for call_id, _ in node_calls:
                operation_id = digest([self.lease.run_id, path, call_id])
                operation = self.journal.operation(self.lease, operation_id)
                if not operation or operation["status"] != "pending" or "job_id" not in operation:
                    continue
                alias = operation["intent"]["alias"]
                binding = self.spec.tools[alias]
                tool = self.engine.tools.resolve(binding.plugin, binding.version)
                state = "cancel_unconfirmed"
                if isinstance(tool, ExternalTool) and tool.cancel:
                    try:
                        async with asyncio.timeout(tool.timeout_seconds):
                            remote = await invoke(tool.cancel, operation["job_id"])
                        state = (
                            remote.status
                            if isinstance(remote, ExternalStatus)
                            else "cancel_unconfirmed"
                        )
                    except Exception:
                        pass
                self.journal.operation(self.lease, operation_id, update={"cancel_status": state})
                self.save("external.cancel", path, operation_id=operation_id, state=state)
