# Evaluate the application you want to build

Start with tasks your users actually bring to the agent. EvoSprig accepts input-only tasks, reference answers, tool requirements, node checks and results from your own environment. The evaluator stays fixed while the optimizer changes selected prompts or skills.

## Start with inputs only

Create `tasks.jsonl` with at least four distinct JSON input objects matching your AgentSpec. Larger, representative sets give a more useful comparison.

```jsonl
{"question":"Which customers account for most of our revenue?"}
{"question":"How did refunds affect October revenue?"}
{"question":"Which region has the strongest repeat purchases?"}
{"question":"Where should we investigate an increase in cancellations?"}
```

```bash
evosprig suite --inputs tasks.jsonl --name sales-tasks --out tasks.yaml \
  --rubric "Check calculations, business relevance and grounding in actual query results."
evosprig improve my-agent/agent.yaml --suite tasks.yaml \
  --method opro --resource instructions --rounds 2 \
  --profile deployment.yaml --max-model-calls 200
```

Studio's **Improve → Create from task inputs** exposes the same workflow. A rubric is optional: the default covers task completion, explicit constraints, factual grounding and usability. No reference answer is required. The task model acts as judge unless you configure a separate model:

```yaml
evaluation:
  judges:
    critic:
      base_url: https://api.example.com/v1
      model: your-judge-model
      api_key_env: JUDGE_API_KEY
```

Set `metric.judge_binding: critic` when several judges are configured. Judge calls share the experiment's token, time and call budget; reports show their separate usage. The judge sees the task, optional references/context, actual output and tool/environment observations. Fields ending in `_base64` are represented by size and content hash in text-only judging/reflection; media must be assessed through tool observations or a custom multimodal scorer. Execution still receives the original payload. It does not see the candidate name, optimization method or evolving instruction text. `repeats: 2` or `3` records repeated judgments and their spread.

A model judgment is useful feedback, not a substitute for an observable business outcome. For bookings, repository changes, SQL correctness or code execution, add environment assertions or your own scorer. Judge confidence is self-reported, not a calibrated probability. Using the same model for tasks and judging can introduce shared blind spots; an independent judge and hard checks help.

## Bring your own task suite

`EvalSuite` has disjoint `search`, `selection`, `release` and optional `test` partitions. `suite` creates these deterministically. You can also assign them yourself in YAML. Search and selection are available to the optimizer; release and test inputs remain outside its context.

A sample supports:

```yaml
id: invoice-017
input: {invoice: "..."}
expected: {total: 125.50, balanced: true}
context: {currency: USD, expense_policy: "Meals need a receipt."}
rubric: "Flag missing dates instead of inventing them."
tags: [expense-policy]
required_tools: [calculate]
responses:
  graph/review:
    text: {from_input: draft}
```

`responses` supplies explicit human-node answers for unattended evaluation. `{from_input: draft}` copies a field from that waiting node's input. Unanswered approvals and jobs that exceed the resume limit are canceled and fail the task; an evaluator never assumes approval.

## Combine checks at different levels

| Metric | What it measures |
| --- | --- |
| `exact`, `contains` | A reference value or required text |
| `tool_called` | A successful tool receipt |
| `json_schema` | The shape of a selected result |
| `llm_judge` | Task quality under a fixed rubric, with written feedback |
| `external` | A named deployment scorer returning a score and feedback |
| `composite` | Weighted checks, optionally with mandatory thresholds |

Use `target: output`, `node`, `trajectory`, `tools` or `environment`. `output_path` selects a nested observation; set it to `""` for the whole value. Node targets use the checkpoint path, for example `graph/analyze`. `reference_path` selects a nested value in the sample's `expected` object.

```yaml
metric:
  kind: composite
  components:
    - kind: exact
      target: environment
      output_path: tests_passed
      reference_path: balanced
      required: true
      threshold: 1
    - kind: llm_judge
      output_path: ""
      weight: 2
      rubric: "Assess completeness and usefulness against the task."
```

Required failures force the composite score to zero. Execution failure or missing required tool receipts also scores zero. Invalid judge JSON or unavailable scorer bindings raise an evaluation error rather than produce a passing grade.

## Connect a scorer or environment

An HTTP scorer receives `{sample, run, observations}` and returns:

```json
{"score":0.8,"feedback":"Four of five business checks passed","confidence":1.0}
```

```yaml
evaluation:
  scorers:
    business:
      endpoint: https://evaluation.example.com/score
      auth_env: SCORER_TOKEN
  environment:
    documents:
      - {title: Policy, text: "...", source: "policy:v3"}
    facts: ["The customer prefers email."]
    memory_writes: true
```

Use `kind: external, scorer: business`. Scorers are deployment bindings; datasets cannot import arbitrary Python. `memory_writes` enables only the native memory-write tools inside each sample's fresh identity. Production user memory is never reused for search.

For an interactive or effectful environment, pass a trusted SDK object to `execute_study(environment=...)` or `Evaluator(environment=...)` implementing `EvaluationEnvironment`:

```python
class Sandbox:
    allow_writes = True

    def __init__(self, session_factory):
        self.session_factory, self.sessions = session_factory, {}

    async def prepare(self, scope, sample, tools):
        session = await self.session_factory(scope)
        self.sessions[scope.user] = session
        await session.seed(sample.input)
        return session.tools

    async def observe(self, scope, sample, result):
        return await self.sessions[scope.user].check_result(result.output)

    async def cleanup(self, scope):
        session = self.sessions.pop(scope.user, None)
        if session:
            await session.close()

```

The session factory belongs to your environment adapter; its tools and checks must supply real isolation and observations. Scope IDs alone cannot sandbox a remote payment service or a host shell. The declarative CLI/Studio supports seeded documents, facts, isolated memory writes and approval responses; arbitrary external write sandboxes use the SDK interface.

## Compare the outputs

```bash
evosprig compare my-agent --study STUDY_ID --workspace .evosprig --out comparison.md
```

The comparison contains paired task inputs, final outputs, scores, model and version identifiers. It omits optimizer conversations and full execution traces. Inspect the exported file before sharing it: application inputs and final answers may still contain your own private data. Studio can also show the paired outputs directly.

Original papers and implementation mappings: [Research references](references.md).
