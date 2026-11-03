# Evolve the application harness

Choose the parts of an application that may change, supply your tasks, and run a search. A candidate can include prompts, skill libraries, Python resources, per-agent harness settings, model choices and workflow topology. EvoSprig executes the complete candidate through its runtime and stores its version and diff.

## Give each agent a harness

```python
builder.node(
    "analyst", "agent", model="main", instructions={"resource": "analysis"},
    tools=["search"], inputs={"question": {"ref": "input.question"}},
    output_schema={"type": "object"},
    harness={
        "max_tool_rounds": 8,
        "tool_errors": "feedback",
        "output_errors": "feedback",
        "max_output_retries": 1,
        "memory": {"tool": "search", "query_input": "question",
                   "limit": 5, "max_chars": 4000},
    },
)
```

Declare `search` as `memory.search`, `memory.recall` or `documents.search`. The memory policy retrieves context before the first model call. Harness fields override the corresponding node defaults; omitted fields retain those defaults. Use `spec_version="0.3"`.

In Studio, select an agent and enable **Use a per-agent harness**. Set tool rounds, tool selection, output recovery and memory retrieval in its inspector.

## Declare the search space

Save this as `search-space.yaml`:

```yaml
fields:
  /graph/nodes/analyst/model:
    kind: choice
    choices: [fast, careful]
  /graph/nodes/analyst/harness/max_tool_rounds:
    kind: integer
    minimum: 2
    maximum: 12
  /graph/nodes/analyst/harness/memory/limit:
    kind: integer
    minimum: 1
    maximum: 10
modules:
  instructions: [resource:analysis]
  execution:
    - /graph/nodes/analyst/model
    - /graph/nodes/analyst/harness/max_tool_rounds
  retrieval: [/graph/nodes/analyst/harness/memory/limit]
```

`fast` and `careful` are model aliases already declared in the AgentSpec. Each pointer must resolve in the initial specification, so configure the harness fields before searching them. Numeric bounds apply to new values; the original value remains available as the baseline. Use `kind: number` for continuous parameters such as temperature. A `choice` can also contain complete structured objects.

```bash
evosprig improve agent.yaml --suite tasks.yaml \
  --method modular_rsi --resource analysis \
  --search-space search-space.yaml --rounds 2 \
  --proposal-output-tokens 4096 --max-evaluations 300 \
  --profile deployment.yaml
```

In Studio, open **Improve → Search space and method settings** and paste the equivalent JSON. The same configuration is available through `StudyConfig(search_space=...)` and the study API. Use `--method-options options.yaml` for method-specific controls.

## Search workflow topology

A graph dimension lets the proposer edit nodes, edges, bounded loops, branches and input mappings:

```yaml
fields:
  /graph: {kind: graph}
tool_grants:
  /new_calculation: [python]
```

Every proposed graph passes AgentSpec validation, including reachability, reference ordering and nesting limits. Existing nodes keep their tool authority. `tool_grants` explicitly assigns declared tool aliases to new or changed node paths; nested paths use `/team/body/worker` or `/team/branch/worker`. Model bindings, application schemas, execution budgets and deployment permissions stay under developer control.

## Evolve executable code

Store a transformation in a code resource:

```python
builder.resource("totals", "code/totals.py", role="code")
builder.tool("python", "code.python")
builder.node("calculate", "code", tool="python", code="totals",
             inputs={"rows": {"ref": "input.rows"}},
             output_schema={"type": "object"})
```

```python
# code/totals.py
def run(inputs):
    amounts = [row["amount"] for row in inputs["rows"]]
    return {"total": sum(amounts), "count": len(amounts)}
```

The built-in interpreter supports JSON values, arithmetic, conditionals, bounded loops, single-generator comprehensions and common string/list/dictionary operations. It executes at most 10,000 instructions, with a 32,000-character program and 65,536-character value limit. Use a deployed sandbox tool with the same `{code, data}` input contract for Python packages, files or network access. Code resources are syntax-checked, versioned and included in standalone exports.

Select `--resource totals` with a harness optimizer to search the implementation. A code node runs whenever the workflow reaches it. An agent can instead call a declared tool when its reasoning requires it.

## Method policies

These are native adaptations of the cited methods to EvoSprig candidates and task evaluation.

| Method | Search behavior | Main controls in `options` |
| --- | --- | --- |
| [SkillOpt](https://arxiv.org/abs/2605.23904) | Anchored, bounded skill patches; rejected-edit memory; protected slow guidance; strict selection gains | `edit_budget`, `edit_chars`, `batch_size`, `slow_every` |
| [Evo-Harness](https://arxiv.org/abs/2608.15071) | Ordered task stream → failure memories → topic/general skill libraries; next tasks discover relevant procedures | `batch_size`, `general_min_tasks`, `max_skills` |
| [AHE](https://arxiv.org/abs/2604.25850) | Diagnose traces, declare predicted fixes and regressions, measure changes, revert failed mechanisms by target | Study `rounds` |
| [Meta-Harness](https://arxiv.org/abs/2603.28052) | Propose from archived implementations, scores and traces; track a score/token frontier | Study `rounds` |
| [RRSI](https://arxiv.org/abs/2609.24972) | Repeated measurements, edit-budget annealing, revision history, mechanism review and score/cost admission | `repetitions`, `proposals`, `delta`, `min_edits`, `max_edits`, `beta0`, `beta1` |
| [ADAS](https://arxiv.org/abs/2408.08435) | Design, critique, implement, evaluate and retain a design archive | Study `rounds` |
| [DarwinX](https://arxiv.org/abs/2608.07545) | Branch mutations and complementary recombination; fresh parent screening and repeated confirmation; preserve solved tasks | `repetitions`, `screen_size`, `merge_every`, `regression_tolerance` |
| [ModularRSI](https://arxiv.org/abs/2609.14857) | Independent module branches, same-task contrasts, diff review, disjoint integration and joint execution checks | `repetitions`, `integration_rounds`; `search_space.modules` |
| [Arbor](https://github.com/RUC-NLPIR/Arbor) | Coordinator expands/selects/prunes hypotheses; experiments start from current trunk; insights propagate to ancestors | `max_depth`, `coordinator_actions` |

SkillOpt and Evo-Harness require attached `skill` resources. Evo-Harness stores discoverable procedures with triggers and source-task IDs inside those resources. RRSI needs reported positive task token costs; its default uncertainty band comes from repeated baseline scores, or set an explicit `delta`. Its novelty term measures newly improved editable targets. ModularRSI assigns each target to one module and uses execution/review gates within branches. DarwinX uses repeated search-task measurements to admit branches and choose its result. Arbor advances the trunk only when both search and selection scores improve.

AHE returns its retained revision; Evo-Harness returns the accumulated library; ModularRSI returns the checked integration. ADAS and Meta-Harness select by validation score. Each method's result then passes the same independent release evaluation and adoption controls.

## Evaluate actions and state

For writing tasks, start from task inputs and an LLM judge. For code or business operations, add execution checks and observable environment state. `evaluation.environment.workspace_writes: true` enables scoped shared documents and peer messages during evaluation. Each sample receives a fresh identity and workspace state. The [industry environment adapter](industry-environments.md) supplies business operations and final-state checks.

See [evaluation](evaluation.md), [method requirements](method-requirements.md) and [optimizer plugins](optimizer-plugins.md).
