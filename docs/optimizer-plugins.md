# Add an evolution algorithm

Implement an async function receiving `EvolutionContext` and `StudyConfig`, then register it. EvoSprig supplies candidate versions, task execution, scoring, budgets and release validation.

## Minimal optimizer

```python
from evosprig.evolution import register_method

async def concise_search(context, *, config):
    selected = context.seed
    best = await context.evaluate(selected, "selection")
    feedback = await context.evaluate(selected, "search")
    for _ in range(config.rounds):
        candidate = await context.json_proposal({
            "resources": selected,
            "tasks": context.view["search"],
            "feedback": feedback,
            "instruction": "Simplify the instructions while preserving task constraints.",
            "style": config.options.get("style", "concise"),
        })
        feedback = await context.evaluate(candidate, "search")
        validation = await context.evaluate(candidate, "selection")
        if validation["score"] > best["score"]:
            selected, best = candidate, validation
        context.emit("method.checkpoint", score=best["score"])
    return {"selected": selected, "selected_score": best["score"],
            "status": "completed"}


def install():
    register_method(
        "concise_search", concise_search,
        title="Concise search", family="instruction search",
        feedback="task inputs and scalar scores",
        source="https://example.org/your-paper",
    )
```

The returned `selected` mapping contains the complete text of every selected resource. `context.version()` validates that set. `context.evaluate()` archives candidates and returns the application's score, outputs and execution observations.

Call `install()` before constructing `StudyConfig` in an embedded application:

```python
from evosprig.evolution.study import StudyConfig

install()
config = StudyConfig(method="concise_search", allowed_resources=["draft", "style"],
                     rounds=2, options={"style": "plain language"})
```

Pass this configuration to `execute_study(...)` alongside the compiled application, `EvalSuite`, model bindings and `StudyStore`. The SDK integration in [test_optimizer_plugins.py](../tests/test_optimizer_plugins.py) exercises the complete path.

## Package a plugin for CLI and Studio

Expose an installer through Python entry points:

```toml
[project.entry-points."evosprig.evolution"]
concise_search = "my_optimizer:install"
```

Install the package into the environment running EvoSprig and restart the server. CLI and Studio discover its method metadata from the same registry. You can then select **Concise search** or run:

```bash
evosprig improve agent.yaml --suite tasks.yaml \
  --method concise_search --resource draft --resource style --rounds 2
```

Packages are trusted server extensions. Method registration rejects duplicate names and synchronous functions.

## Context contract

| Interface | Purpose |
| --- | --- |
| `seed`, `allowed` | Initial resource texts and selected resource names |
| `view["search"]`, `view["selection"]` | Frozen optimization tasks |
| `evaluate(texts, split, samples=None)` | Run the application on an allowed split or subset |
| `propose(messages, json_output=False)` | Budgeted proposal-model request |
| `json_proposal(payload)` | Request and validate a full resource mapping |
| `archive(texts)`, `version(texts)` | Store a candidate or compile its snapshot |
| `emit(type, **data)` | Send progress to the study UI |
| `meter` | Shared call, token, candidate, evaluation and time limits |

Use the context model and evaluation methods so calls count toward the study budget. Propagate `BudgetExceeded` and cancellation. The study runner validates the selected version on release/test tasks and computes the release gate; the user adopts the version separately.

## Validate a method

Cover invalid candidates, budget exhaustion, cancellation, selection behavior and a complete `execute_study` run. Add the original paper to [references](references.md) and describe the implemented mechanism in the [method table](evolution.md). Use a small application task set to demonstrate its changes and resulting outputs.

## Structured candidate plugins

Register `supports_structured=True` for an optimizer that accepts `StudyConfig.search_space`.
Then `context.seed` and every proposal have the shape `{"resources": {...}, "fields": {...}}`.
Use `context.version(candidate)` to validate bounds, graph structure and tool authority;
`context.evaluate(candidate, split)` runs that exact snapshot. Resource-only plugins keep
their existing name-to-text mapping. Module ownership is available as
`context.search_space.modules`; `resource:name` targets identify resources and JSON pointers identify fields.

Keep method state separate from target resources. `context.emit("method.checkpoint", ...)`
stores progress, while the returned `selected` candidate controls release evaluation.
