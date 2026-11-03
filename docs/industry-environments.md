# Build industry agents with their own working environment

An industry agent needs more than a question and an answer. It may need to read an application, check a policy, update a record and request approval. EvoSprig connects environment construction, business tools and outcome-based evaluation so you can develop that whole workflow.

![Industry environment construction and agent development](../examples/industry-environment-builder/assets/overview.svg)

Choose your starting point:

- **You have a validated IndustryBench environment:** [prepare an agent and task suite](#use-an-existing-environment).
- **You need a new business process:** [draft its environment](#construct-a-new-environment), implement and validate it, then prepare the agent.
- **You have another simulator:** implement the [evaluation environment protocol](evaluation.md#connect-a-scorer-or-environment).

## Use an existing environment

Install your IndustryBench distribution, or set `INDUSTRYBENCH_ROOT` to its package root. It supplies `industrybench.session`, `industrybench.registry`, `industrybench.evaluation`, the domain engines and frozen cases.

```bash
export INDUSTRYBENCH_ROOT=/path/to/industry-agent
evosprig industry prepare --industry government --limit 12 --out my-industry-agent
```

Choose `finance`, `government` or `manufacturing`. The command creates:

| File | Purpose |
| --- | --- |
| `agent.yaml` | Native tool-using agent |
| `prompts/procedure.md` | Operating instructions you can edit and evolve |
| `suite.yaml` | Disjoint search, selection and release tasks |
| `deployment.yaml` | Model, business tools and environment settings |

The agent sees the case, public procedure and tool schemas. Reference answers stay with the evaluator. A fresh sandbox is created for each task; recorded actions are replayed against fixed business checks.

## Evaluate, then improve

Set the model credential referenced in `deployment.yaml`:

```bash
evosprig evaluate my-industry-agent/agent.yaml \
  --suite my-industry-agent/suite.yaml \
  --profile my-industry-agent/deployment.yaml

evosprig improve my-industry-agent/agent.yaml \
  --suite my-industry-agent/suite.yaml \
  --profile my-industry-agent/deployment.yaml \
  --method reflexion --resource procedure --rounds 2 \
  --max-evaluations 100 --timeout 1800
```

The optimizer proposes instruction changes, executes the agent and uses the environment's outcomes to select candidates. Compare edits and results before enabling a version. [Choose another evolution method](evolution.md).

For the canvas, start the same project and profile:

```bash
evosprig serve --project my-industry-agent/agent.yaml \
  --profile my-industry-agent/deployment.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/industry
```

Use **Improve** with the generated suite. Industry sandboxes are allocated by evaluation; ordinary **Run** executes the workflow without an evaluation session.

## Construct a new environment

The [environment builder](../examples/industry-environment-builder/) turns a business brief into seven connected outputs:

**Context → schema → procedures → tool graph → data → APIs → implementation drafts → human review.**

```bash
evosprig industry synthesis --templates /path/to/industry-agent/synthesis \
  --scene government --out environment-builder

evosprig serve --project environment-builder/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/industry-builder
```

Submit, for example:

```json
{"brief":"Build a benefits application process with eligibility checks, exception review and a recorded final decision."}
```

Template scenes include `loan`, `account`, `credit_cards`, `deposit`, `invest`, `government` and `manufacturing`. Each stage is a model node with an editable prompt and bounded output. The generated project defaults to seven model calls, 8,192 output tokens per call and a 200,000-token total budget; adjust these in the project for your domain.

After review, integrate the implementation drafts with the environment engine. Run its reference and validation tools, then freeze the cases and business answers. This validated installation becomes the input to `industry prepare`.

## Business tool interface

| Tool | Agent operation |
| --- | --- |
| `industry.materials` | Read the case and operating procedure |
| `industry.search` | Discover relevant tool schemas |
| `industry.invoke` | Call a discovered tool in the active sandbox |

Invocations use journaled idempotency keys. Each session owns its engine thread for creation, calls and cleanup, including thread-affine databases. Final checks use the recorded business outcome.

## Tune task size and budgets

`industry prepare` assigns approximately half the cases to search and reserves two for release; the rest select candidates. At least four cases are required. Use a representative task suite for your release decision.

| Setting | Default | Purpose |
| --- | --- | --- |
| Agent `max_tool_rounds` | 192 | Tool-use rounds per case |
| Agent `max_model_calls` | 200 | Model-call cap within the shared budget |
| `evaluation.industry.search_limit` | 8 | Schemas returned by a tool search |
| `evaluation.industry.max_calls` | 256 | Business-tool call cap |
| `evaluation.industry.timeout_seconds` | 30 | Timeout per business-tool call |
| `evaluation.environment.max_concurrent_samples` | 1 | Independent evaluation sessions |

`evaluation.industry.allowed_cases` restricts the accessible cases. Sandbox write permission applies to simulated business operations. The generated profile contains all selected case IDs, and the suite keeps the three evaluation splits separate.

[Industry assistant](../examples/industry-assistant/) · [Environment builder](../examples/industry-environment-builder/) · [Evaluation guide](evaluation.md)
