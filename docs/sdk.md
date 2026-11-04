# Python SDK and AgentSpec reference

[English](sdk.md) · [简体中文](zh-CN/sdk.md) · [Documentation](README.md)

## Builder

Import `Builder` from `evosprig.sdk`. Methods return the builder so calls can be chained; `build_spec()` returns a validated `AgentSpec`.

| Method | Parameters and behavior |
| --- | --- |
| `Builder(project_id, input_schema, output_schema, *, spec_version="0.1")` | Create the graph; use `"0.3"` for map and current application features |
| `default_model(binding, requires=None)` | Declare `main`; missing node models inherit it recursively; default capability is `text` |
| `model(name, binding, requires=None)` | Declare a node-visible alias for a deployment connection |
| `tool(name, plugin, version="1")` | Declare a tool alias and plugin contract |
| `resource(name, path, role="prompt")` | Declare a prompt, skill or code file relative to the spec; duplicate resource names are rejected |
| `skill(name, path)` | Shorthand for a resource with `role="skill"` |
| `node(node_id, node_type, *, entry=False, **config)` | Add one node; the first node becomes entry unless another explicitly sets it |
| `edge(source, target, *, when=None)` | Add a dependency; `when=True/False` selects a condition branch |
| `map(node_id, *, items, body, output_schema, inputs=None, max_items=32, carry=None)` | Add a map; `carry` feeds the previous item's output into the next item |
| `output(**bindings)` | Set the graph's output references or literal values |
| `execution(**limits)` | Set run budgets and execution policy |
| `build_spec()` | Copy, resolve default models and validate; leaves the builder data unchanged |

See the runnable [first agent](tutorials/first_agent.py) and [Comic Studio builder](../examples/comic-studio/build_agent.py).

## AgentSpec and bindings

The complete machine-readable contract is [AgentSpec JSON Schema](assets/agent-spec.schema.json), including every field, enum, default and bound. The Python definitions are in [core/spec.py](../src/evosprig/core/spec.py).

| Top-level field | Meaning |
| --- | --- |
| `spec_version`, `id` | Contract version and application identity |
| `input_schema`, `output_schema` | JSON Schemas for application input and output |
| `models` | Alias → deployment binding and required capabilities |
| `tools` | Alias → plugin ID and version |
| `resources` | Name → relative file path and role |
| `graph` | Entry, nodes, edges and output bindings |
| `execution` | Step, model, token, time and side-effect policy |

Inputs use `{"ref": "input.story"}` or `{"ref": "nodes.writer.output.text"}`. Use `{"value": ...}` for a literal. Optional references accept `optional: true` and `default`. A subflow's `input` is its own input object. A map body receives `item`, `index` and `context`; a loop passes its body output to the next iteration. See [graph execution](architecture.md) and [the map example](../examples/comic-studio/agent.yaml).

## Node types

Every node has `type`, `inputs` and `output_schema`. The schema validates required combinations and rejects unknown fields.

| Type | Role and important fields |
| --- | --- |
| `model` | One model task: `model`, `instructions`, `skills`, `response_format`, `image_inputs` |
| `agent` | A model with a tool loop: model fields plus `tools`, `harness`, optional `mailbox` |
| `tool` | Required deterministic call: `tool` and typed inputs |
| `code` | Restricted JSON transformation: `tool`, `code` resource, `code_max_value_chars` |
| `transform` | Return resolved inputs as an object |
| `condition` | Evaluate `condition`; select edges with `when` |
| `join` | Merge arrivals; `join` is `all` or `selected` |
| `loop` | Execute `body` up to `max_iterations`; `until` can stop early |
| `parallel` | Execute named `branches` and collect their outputs |
| `map` | Execute `body` for `items`; `max_items` bounds the input list; optional `carry` |
| `human` | Pause for a response checked against `output_schema` |

A structured `harness` applies to agent nodes. Non-null harness values override the corresponding node fields; omitted values preserve them. Node token limits override the application output limit, within the shared run budget. [Prompt, skill and harness fields](agent-resources.md).

## Compile, save and run

`save_spec(spec, path)` writes YAML; `load_spec(path)` reads and validates it. `compile_agent(spec, root=".")` freezes a loaded spec and the resource files relative to `root`; for a file, use `compile_agent(load_spec(path), path.parent)`. `compile_snapshot(spec, resources)` freezes resource text already held in memory. These functions are in `evosprig.core.spec` and `evosprig.core.version` respectively.

`Runtime` is imported from `evosprig.core.runtime`. Construct it with a model mapping and optional `ToolRegistry`; keyword options are `journal`, `allow_writes=False` and `lease_seconds=30.0`. Use the deployment helpers in `evosprig.config` to construct model/tool bindings and `prepare_services(profile)` before a local-model run.

| Runtime operation | Result |
| --- | --- |
| `await runtime.run(version, inputs, *, run_id=None, scope=None, cancel=None, on_event=None, shutdown=None)` | Start/resume execution and return `RunResult` |
| `runtime.create_run(version, inputs, *, run_id=None, scope=None, context=None)` | Persist a run for a worker to execute |
| `await runtime.resume(run_id, *, scope=None, cancel=None, on_event=None, shutdown=None)` | Continue from its frozen version and checkpoint |
| `runtime.get(run_id, scope=None)` | Read current state |
| `await runtime.cancel_run(run_id, *, scope=None)` | Request cancellation and return current state |
| `runtime.create_event_run(version, inputs, trigger, *, scope=None)` | Create an idempotent event-triggered run |

`RunResult` contains `run_id`, `agent_version`, `status`, `output`, `error`, `events`, `usage`, `duration_seconds` and `waiting`. Use `to_dict()` for serialization. Waiting for a tool or human response preserves completed work; use [recovery](durable-runtime.md) for continuation and reconciliation.

## Command line

`evosprig --help` lists all command groups. `evosprig COMMAND --help` lists options. The core commands are:

```bash
evosprig validate agent.yaml
evosprig run agent.yaml --profile deployment.yaml --workspace .evosprig --input-file task.json
evosprig runs --workspace .evosprig
evosprig inspect RUN_ID --workspace .evosprig
evosprig resume RUN_ID --workspace .evosprig
evosprig cancel RUN_ID --workspace .evosprig
evosprig serve --project agent.yaml --profile deployment.yaml --studio-dir apps/studio/dist --port 18766
evosprig export agent.yaml --target python --out application
evosprig import application.zip --out imported
```

Use `--mock` for a fixture run and `--allow-writes` for configured write tools. `serve` defaults to four concurrent runs; change `--max-concurrent-runs` to fit service capacity. Other command groups: [services](local-models.md), [data and evaluation](evaluation.md), [evolution](evolution.md), [ComfyUI](comfyui.md), [industry environments](industry-environments.md).
