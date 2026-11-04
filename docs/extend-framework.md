# Extend EvoSprig

[English](extend-framework.md) · [简体中文](zh-CN/extend-framework.md) · [Documentation](README.md)

Core contracts live in `src/evosprig/core`. Concrete model, tool and memory implementations live in `plugins`; optimization algorithms live in `evolution`. CLI, Studio and exported applications use the same runtime.

## Extension contracts

| Add a… | Implement | Register or bind | Starting point |
| --- | --- | --- | --- |
| Self-evolution algorithm | Async optimizer receiving `EvolutionContext` | `register_method` / `evosprig.evolution` entry point | [Optimizer plugins](optimizer-plugins.md) |
| Model provider | `ModelProvider.complete(ModelRequest) → ModelResponse` | Pass it in `Runtime(models=...)`; add deployment restoration for CLI | [OpenAI-compatible provider](../src/evosprig/plugins/openai_compatible.py) |
| Local tool | `Tool` with input/output JSON schemas | `ToolRegistry.register` and `Builder.tool` | [Tool contracts](tools.md) |
| Long-running service | `ExternalTool.submit`, `poll`, optional `cancel` | Registry or `external_http` profile binding | [Media service](../apps/media-service/) |
| Memory backend | `MemoryStore` | Bind scope outside model arguments; register memory tools | [Memory interfaces](../src/evosprig/core/memory.py) |
| Task scorer | A scorer callable returning the declared metric result | `Evaluator(..., scorers=...)` | [Evaluation](evaluation.md) |
| Evaluation environment | `prepare`, `observe`, `cleanup` | `Evaluator(..., environment=...)` | [Environment protocol](../src/evosprig/evaluation/environment.py) |
| Application | AgentSpec, resources and tool bindings | CLI / Studio / SDK | [Application developer guide](build-applications.md) |

## Runtime changes

A new node behavior touches the specification, engine, canvas mapping and editor. Keep these interfaces aligned:

- `core/spec.py`: typed configuration, references and graph validation.
- `core/engine.py`: execution, checkpoints, cancellation and shared budgets.
- `server/canvas.py` and `apps/studio`: presentation and editing.
- `exporters/python.py`: modules and bindings needed by standalone applications.

Test recovery after an interrupted operation, including whether retrying it can repeat a write. `ToolRejectedError` is for a write rejected before any side effect; ambiguous failures use the existing reconciliation path. See [durable runtime](durable-runtime.md).

## Shared state and applications

[WorkspaceStore](shared-workspaces.md) gives tools and browser clients a common revisioned document store. Memory supplies scoped facts and retrieval; project resources supply versioned agent instructions. Use the store appropriate to the data's lifetime.

The [CoworkOS reproduction](../examples/cowork/) demonstrates a main agent, runtime-coordinated specialists, shared document editing and persisted wake-ups. Its web interface calls the standard project/run/document APIs.

## Development and review

Follow [Contributing](../CONTRIBUTING.md) for installation and checks. Include a runnable example for a new public capability, update its guide, and run tests covering the changed behavior. Keep the English and Chinese user-facing interfaces aligned.
