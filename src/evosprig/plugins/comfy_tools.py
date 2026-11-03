"""Typed, composable ComfyUI node tools and asynchronous execution bindings."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from evosprig.core.protocols import Tool, ToolFeedbackError
from evosprig.core.spec import Contract
from evosprig.integrations.comfyui import (
    ComfyWorkflow,
    accepts_type,
    fields,
    input_schema,
    is_widget,
)

HANDLE = {
    "type": "object", "required": ["node_id", "slot", "type", "prompt"],
    "properties": {"node_id": {"type": "string"}, "slot": {"type": "integer", "minimum": 0},
                   "type": {"type": "string"}, "prompt": {"type": "object"}},
    "additionalProperties": False,
}


class ComfyNodeConfig(Contract):
    kind: Literal["comfy_node"] = "comfy_node"
    name: str
    version: str = "1"
    node_id: str
    class_type: str
    description: str = "Configure a ComfyUI node and connect its outputs."
    info: dict
    defaults: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid(self):
        if not self.node_id or not self.class_type or "input" not in self.info:
            raise ValueError("ComfyUI node binding requires an ID, class and object_info schema")
        known = {name for name, _, _ in fields(self.info)}
        if self.defaults.keys() - known:
            raise ValueError("node defaults contain unknown inputs")
        return self


class ComfyParameter(Contract):
    model_config = ConfigDict(serialize_by_alias=True)
    node_id: str
    also_nodes: list[str] = Field(default_factory=list, max_length=32)
    input_name: str | None = None
    description: str = ""
    kind: Literal["input", "enabled"] = "input"
    value_schema: dict = Field(default_factory=dict, alias="schema")


class ComfyReferenceSlot(Contract):
    node_id: str
    input_name: str = "image"


class ComfyRecipeConfig(Contract):
    """A saved graph with an explicit set of agent-editable controls."""

    kind: Literal["comfy_recipe", "comfy_recipe_info"] = "comfy_recipe"
    name: str
    version: str = "1"
    description: str = "Prepare a render using the saved graph and named controls."
    workflow: dict
    object_info: dict
    outputs: list[str] = Field(min_length=1)
    parameters: dict[str, ComfyParameter] = Field(default_factory=dict)
    reference_slots: list[ComfyReferenceSlot] = Field(default_factory=list, max_length=16)
    audio_slots: list[ComfyReferenceSlot] = Field(default_factory=list, max_length=16)
    video_slots: list[ComfyReferenceSlot] = Field(default_factory=list, max_length=16)


def comfy_recipe_tool(config: ComfyRecipeConfig) -> Tool:
    from jsonschema import Draft202012Validator

    workflow = ComfyWorkflow(config.workflow, config.object_info)
    controls, defaults = {}, {}
    for alias, parameter in config.parameters.items():
        for node_id in [parameter.node_id, *parameter.also_nodes]:
            if node_id not in workflow.nodes:
                raise ValueError(f"unknown recipe node: {node_id}")
        if parameter.also_nodes and parameter.kind != "enabled":
            raise ValueError("group controls can only enable or bypass nodes")
        if parameter.kind == "enabled":
            if not workflow.ui:
                raise ValueError("recipe switches require a UI workflow")
            native = {"type": "boolean"}
        else:
            if workflow.ui and any(
                port["name"] == parameter.input_name and port.get("link") is not None
                for port in workflow.nodes[parameter.node_id].get("inputs", [])
            ):
                raise ValueError(
                    f"recipe control {alias} targets a connected input; expose its source node instead"
                )
            info = config.object_info.get(workflow.class_type(parameter.node_id), {})
            descriptor = next((desc for name, desc, _ in fields(info) if name == parameter.input_name), None)
            if descriptor is None:
                raise ValueError(f"unknown recipe input: {alias}")
            native = input_schema(descriptor)
        controls[alias] = {"allOf": [native, parameter.value_schema]} if parameter.value_schema else native
        if parameter.description:
            controls[alias]["description"] = parameter.description
        if parameter.kind == "enabled":
            defaults[alias] = workflow.nodes[parameter.node_id].get("mode", 0) == 0
        elif workflow.ui:
            saved = workflow._widgets(parameter.node_id).get(parameter.input_name)
            if saved is not None:
                defaults[alias] = deepcopy(saved[0])
        elif parameter.input_name in workflow.nodes[parameter.node_id]["inputs"]:
            defaults[alias] = deepcopy(workflow.nodes[parameter.node_id]["inputs"][parameter.input_name])
    reference_groups = {"reference_images": config.reference_slots,
                        "reference_audio": config.audio_slots, "reference_videos": config.video_slots}
    slot_ids = [slot.node_id for slots in reference_groups.values() for slot in slots]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("each reference slot must use a distinct loader node")
    for slots in reference_groups.values():
        for slot in slots:
            if not workflow.ui or slot.node_id not in workflow.nodes:
                raise ValueError("reference slots require existing UI loader nodes")
            if slot.input_name not in workflow._widgets(slot.node_id):
                raise ValueError("reference slot must name a saved loader widget")
    schema = {"type": "object", "properties": {
        "controls": {"type": "object", "properties": controls, "additionalProperties": False},
    }, "additionalProperties": False}
    for name, slots in reference_groups.items():
        if slots:
            schema["properties"][name] = {
                "type": "array", "items": {"type": "string", "minLength": 1}, "maxItems": len(slots),
            }

    if config.kind == "comfy_recipe_info":
        def describe():
            return deepcopy({"controls": schema["properties"]["controls"], "defaults": defaults,
                             "reference_limits": {name: len(slots) for name, slots in reference_groups.items()}})
        return Tool(config.name, "Read the render controls, saved defaults and reference limits.",
                    {"type": "object", "properties": {}, "additionalProperties": False},
                    {"type": "object", "required": ["controls", "defaults", "reference_limits"]},
                    describe, version=config.version)

    def prepare(controls=None, reference_images=None, reference_audio=None, reference_videos=None):
        arguments = {"controls": controls or {}}
        for name, values in (("reference_images", reference_images), ("reference_audio", reference_audio),
                             ("reference_videos", reference_videos)):
            if values is not None:
                arguments[name] = values
        Draft202012Validator(schema).validate(arguments)
        current = ComfyWorkflow(config.workflow, config.object_info)
        # Group presets apply first; explicit node switches override the preset.
        # Apply selectors before their nested controls, independent of JSON order.
        pending = list((controls or {}).items())
        pending.sort(key=lambda item: (
            0 if config.parameters[item[0]].also_nodes else 1,
            (config.parameters[item[0]].input_name or "").count("."),
        ))
        for alias, value in pending:
            parameter = config.parameters[alias]
            if parameter.kind == "enabled":
                for node_id in [parameter.node_id, *parameter.also_nodes]:
                    current.set_enabled(node_id, value)
            else:
                current.set_input(parameter.node_id, parameter.input_name, value)
        for name, slots in reference_groups.items():
            if name in arguments:
                values = arguments[name]
                for index, slot in enumerate(slots):
                    current.set_enabled(slot.node_id, index < len(values))
                    if index < len(values):
                        current.set_input(slot.node_id, slot.input_name, values[index])
        return {"prompt": current.compile(config.outputs), "controls": controls or {}}

    return Tool(config.name, config.description, schema,
                {"type": "object", "required": ["prompt", "controls"],
                 "properties": {"prompt": {"type": "object"}, "controls": {"type": "object"}}},
                prepare, version=config.version)


def comfy_node_tool(config: ComfyNodeConfig) -> Tool:
    properties, required = {}, []
    for name, descriptor, needed in fields(config.info):
        schema = input_schema(descriptor)
        options = descriptor[1] if len(descriptor) > 1 else {}
        # The execution graph stays in JSON; GPU tensors remain inside ComfyUI.
        if not is_widget(descriptor) or options.get("forceInput"):
            schema = deepcopy(HANDLE)
        else:
            schema = {"anyOf": [schema, deepcopy(HANDLE)]}
        if name in properties:
            properties[name] = {"anyOf": [properties[name], schema]}
        else:
            properties[name] = schema
        if needed and name not in config.defaults:
            required.append(name)

    def configure(**arguments):
        values, prompt = {**deepcopy(config.defaults), **arguments}, {}
        declared = {name: (desc, needed) for name, desc, needed in fields(config.info, values)}
        values = {key: value for key, value in values.items() if key in declared}
        for name, (desc, needed) in declared.items():
            if needed and name not in values:
                options = desc[1] if len(desc) > 1 else {}
                if "default" not in options:
                    raise ToolFeedbackError("missing_input", f"{name} is required for the selected mode")
                values[name] = deepcopy(options["default"])
        for name, value in list(values.items()):
            if isinstance(value, dict) and set(value) == {"node_id", "slot", "type", "prompt"}:
                expected = declared[name][0][0]
                if not accepts_type(expected, value["type"]):
                    raise ToolFeedbackError("port_type", f"{name} requires {expected}, got {value['type']}")
                source = value["prompt"].get(value["node_id"])
                if not source:
                    raise ToolFeedbackError("missing_source", f"{name}: source node is missing")
                for key, node in value["prompt"].items():
                    if key in prompt and prompt[key] != node:
                        raise ToolFeedbackError("graph_conflict", f"conflicting definitions for node {key}")
                    prompt[key] = deepcopy(node)
                values[name] = [value["node_id"], value["slot"]]
            else:
                from jsonschema import Draft202012Validator

                Draft202012Validator(input_schema(declared[name][0])).validate(value)
        if config.node_id in prompt:
            raise ToolFeedbackError("cycle", "a node cannot depend on itself")
        prompt[config.node_id] = {"class_type": config.class_type, "inputs": values}
        return {"prompt": prompt, **{
            f"output_{slot}": {"node_id": config.node_id, "slot": slot, "type": kind, "prompt": prompt}
            for slot, kind in enumerate(config.info.get("output", []))
        }}

    return Tool(config.name, config.description,
                {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
                {"type": "object", "properties": {"prompt": {"type": "object"}, **{
                    f"output_{slot}": HANDLE for slot, _ in enumerate(config.info.get("output", []))}},
                 "required": ["prompt"]}, configure, version=config.version)


def import_comfy_spec(workflow: ComfyWorkflow, project_id: str = "comfy-workflow", *, server: str | None = None) -> dict:
    """Expose each executable node as a native tool node, with deployment bindings."""
    from evosprig.integrations.comfyui import is_link
    from evosprig.sdk.builder import Builder

    prompt = workflow.compile()
    builder = Builder(project_id, {"type": "object"}, {"type": "object"}, spec_version="0.3")
    builder.node("start", "transform", inputs={}, output_schema={"type": "object"})
    aliases = {key: f"comfy_{index}" for index, key in enumerate(prompt, 1)}
    bindings, layout, connected = {}, {"start": {"x": 0, "y": 0}}, set()
    for key, node in prompt.items():
        if node["class_type"] not in workflow.object_info:
            raise ValueError(f"missing object_info for {node['class_type']}")
        alias = aliases[key]
        defaults = {k: v for k, v in node["inputs"].items() if not is_link(v)}
        config = ComfyNodeConfig(name=f"comfy.node.{alias}", node_id=key, class_type=node["class_type"],
                                 info=workflow.object_info[node["class_type"]], defaults=defaults,
                                 description=node.get("_meta", {}).get("title", node["class_type"]))
        tool = comfy_node_tool(config)
        bindings[config.name] = config.model_dump(mode="json")
        builder.tool(alias, config.name)
        inputs, parents = {}, set()
        for name, value in node["inputs"].items():
            if is_link(value):
                parent = aliases[value[0]]
                inputs[name] = {"ref": f"nodes.{parent}.output.output_{value[1]}"}
                parents.add(parent)
                connected.add(parent)
            else:
                inputs[name] = {"value": value}
        builder.node(alias, "tool", tool=alias, inputs=inputs, output_schema=tool.output_schema)
        for parent in parents or {"start"}:
            builder.edge(parent, alias)
        source = workflow.nodes[key]
        position = source.get("pos", [len(layout) * 280, 120])
        if isinstance(position, dict):
            position = [position.get("0", 0), position.get("1", 0)]
        layout[alias] = {"x": float(position[0]), "y": float(position[1])}
    sinks = {alias: {"ref": f"nodes.{alias}.output.prompt"} for alias in aliases.values()
             if alias not in connected}
    if server:
        config = ComfyJobConfig(name="comfy.render", base_url=server)
        bindings[config.name] = config.model_dump(mode="json")
        builder.tool("render", config.name)
        builder.node("collect", "transform", inputs=sinks, output_schema={"type": "object"})
        for alias in sinks:
            builder.edge(alias, "collect")
        builder.node("render", "tool", tool="render", inputs={"parts": {"ref": "nodes.collect.output"}},
                     output_schema={"type": "object"})
        builder.edge("collect", "render").output(outputs={"ref": "nodes.render.output"})
    else:
        builder.output(**sinks)
    builder.execution(max_steps=min(1000, 2 * len(prompt) + 8), max_model_calls=0)
    if server:
        builder.execution(max_steps=min(1000, 2 * len(prompt) + 8), max_model_calls=0,
                          allow_side_effects=True, timeout_seconds=3600)
    return {"spec": builder.build_spec().model_dump(mode="json"), "resources": {}, "layout": layout,
            "bindings": {"models": {}, "tools": bindings}, "node_map": aliases,
            "workflow": workflow.export()}


class ComfyJobConfig(Contract):
    kind: Literal["comfy_job"] = "comfy_job"
    name: str
    version: str = "1"
    base_url: str = "http://127.0.0.1:8188"
    auth_env: str | None = None
    dedicated: bool = False
    timeout_seconds: float = Field(default=30, gt=0, le=600)
    job_timeout_seconds: float = Field(default=7200, gt=0, le=86400)


def comfy_job_tool(config: ComfyJobConfig, database, scope, *, transport=None):
    import json
    import sqlite3
    from contextlib import contextmanager
    from pathlib import Path

    from evosprig.core.protocols import ExecutionError, ExternalStatus, ExternalTool
    from evosprig.core.spec import canonical_json, digest
    from evosprig.integrations.comfy_client import ComfyClient, ComfyValidationError

    client = ComfyClient(config.base_url, auth_env=config.auth_env, dedicated=config.dedicated,
                         transport=transport, timeout=config.timeout_seconds)
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    owner = digest([scope.project, scope.user, scope.tenant, config.name, config.base_url])

    @contextmanager
    def connect():
        db = sqlite3.connect(database, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS comfy_jobs (owner TEXT, operation TEXT, request_hash TEXT NOT NULL, prompt_id TEXT, PRIMARY KEY(owner,operation))")
        if "rejection" not in {row[1] for row in db.execute("PRAGMA table_info(comfy_jobs)")}:
            db.execute("ALTER TABLE comfy_jobs ADD COLUMN rejection TEXT")

    async def submit(*, idempotency_key, prompt=None, parts=None):
        if (prompt is None) == (parts is None):
            raise ExecutionError("provide either prompt or parts")
        if parts is not None:
            prompt = {}
            for graph in parts.values():
                for key, value in graph.items():
                    if key in prompt and prompt[key] != value:
                        raise ExecutionError(f"conflicting ComfyUI node {key}")
                    prompt[key] = value
        ComfyWorkflow(prompt).compile()
        fingerprint = digest(prompt)
        # Reserve before the network call. A lost response is reconciled from the
        # queue/history; an unresolved reservation never triggers another render.
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT request_hash,prompt_id,rejection FROM comfy_jobs WHERE owner=? AND operation=?", (owner, idempotency_key)).fetchone()
            if previous and previous[0] != fingerprint:
                raise ExecutionError("ComfyUI operation was reused with different inputs")
            fresh = previous is None
            if fresh:
                db.execute("INSERT INTO comfy_jobs (owner,operation,request_hash) VALUES(?,?,?)", (owner, idempotency_key, fingerprint))
        if previous and previous[2]:
            raise ComfyValidationError(previous[2])
        if previous and previous[1]:
            return previous[1]
        operation = digest([owner, idempotency_key])
        if not fresh:
            prompt_id = await client.find_operation(operation)
            if prompt_id is None:
                raise ExecutionError("ComfyUI submission is unresolved; inspect the server queue/history before retrying")
        else:
            try:
                prompt_id = await client.submit(prompt, client_id=owner, operation_id=operation)
            except ComfyValidationError as error:
                with connect() as db:
                    db.execute("UPDATE comfy_jobs SET rejection=? WHERE owner=? AND operation=?",
                               (str(error), owner, idempotency_key))
                raise
        with connect() as db:
            db.execute("UPDATE comfy_jobs SET prompt_id=? WHERE owner=? AND operation=?", (prompt_id, owner, idempotency_key))
        return prompt_id

    async def poll(job_id):
        status = await client.status(job_id)
        if status["status"] == "unknown":
            raise ExecutionError("ComfyUI job is absent from queue and history; inspect the server")
        return ExternalStatus("pending" if status["status"] in {"queued", "running"} else status["status"],
                              status.get("output"),
                              json.dumps(status["error"])[:2000] if status.get("error") else None)

    # Validate that persisted connection settings contain no embedded credential.
    from evosprig.core.version import check_public_text

    check_public_text(canonical_json(config.model_dump()))
    return ExternalTool(config.name, "Render a composed ComfyUI graph and return its saved outputs.",
                        {"type": "object", "properties": {"prompt": {"type": "object"},
                            "parts": {"type": "object", "additionalProperties": {"type": "object"}}},
                         "oneOf": [{"required": ["prompt"]}, {"required": ["parts"]}],
                         "additionalProperties": False},
                        {"type": "object"}, submit, poll, client.cancel,
                        version=config.version, timeout_seconds=config.timeout_seconds,
                        job_timeout_seconds=config.job_timeout_seconds)
