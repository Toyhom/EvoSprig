# Industry agents and evaluation environments

Connect an IndustryBench installation to develop agents for finance, government services and manufacturing. Every evaluation task gets a fresh sandbox, an operating procedure and discoverable business tools. The evaluator replays the recorded actions against the environment's frozen business criteria.

## Prepare an application

Install your IndustryBench distribution, or point `INDUSTRYBENCH_ROOT` at its local package root. The installation must provide `industrybench.session`, `industrybench.registry` and `industrybench.evaluation`, along with its domain engines and frozen cases.

```bash
export INDUSTRYBENCH_ROOT=/path/to/industry-agent
evosprig industry prepare --industry government --limit 12 --out my-industry-agent
```

This creates a native agent, editable procedure instructions, a deployment profile and disjoint search/selection/release tasks. The default split uses approximately half the cases for search and reserves two for release. The generated business agent allows up to 192 tool rounds and 200 model calls within its shared token/time budget; lower these limits for small tasks. Use a larger representative suite for release decisions. The generated allowlist confines evaluation to those cases.

Set the model credential referenced by `deployment.yaml`, then evaluate or improve:

```bash
evosprig evaluate my-industry-agent/agent.yaml \
  --suite my-industry-agent/suite.yaml \
  --profile my-industry-agent/deployment.yaml

evosprig improve my-industry-agent/agent.yaml \
  --suite my-industry-agent/suite.yaml --profile my-industry-agent/deployment.yaml \
  --method reflexion --resource procedure --rounds 2 \
  --max-evaluations 100 --timeout 1800
```

The same profile enables industry evaluation in Studio's Improve tab. Ordinary `run` does not allocate an evaluation sandbox; use `evaluate` to execute the business agent in this environment.

## What the agent can see

- `industry.materials`: public task observation and operating procedure.
- `industry.search`: relevant tool schemas, with a default limit of eight.
- `industry.invoke`: a discovered tool, executed in the active sandbox with a journaled idempotency key.

Reference answers are kept inside the evaluator. A claimed success in the final message cannot replace a successful business-state check. Each session owns its engine thread, including creation and cleanup, to support thread-affine database implementations.

`evaluation.industry` configures `root_env`, `allowed_cases`, `search_limit`, `max_calls` (256 by default) and tool `timeout_seconds` (30). `evaluation.environment.max_concurrent_samples` defaults to one and can be increased for independent cases. This environment permits its own simulated writes; it does not grant permission to unrelated write tools.

## Draft a new industry environment

Use the local system's synthesis templates to create a normal EvoSprig workflow:

```bash
evosprig industry synthesis --templates /path/to/industry-agent/synthesis \
  --scene government --out environment-builder
evosprig run environment-builder/agent.yaml \
  --input '{"brief":"Design a permit-processing environment with explicit eligibility rules"}'
```

The workflow produces context, schemas, SOPs, an API graph, data, API definitions and implementation drafts, followed by a human review node. Each stage is an editable model node with bounded output and total budgets. Running it uses your configured model API.

After review, integrate the drafts into your environment engine, run its reference/validation tools and freeze the business answers. Connect that validated installation with `industry prepare`. Draft generation does not automatically execute generated Python or certify a new environment.

For another simulator, implement the [evaluation environment protocol](evaluation.md#connect-a-scorer-or-environment) or expose a deployment-owned scorer. Your application, evaluator and resource search continue to use the same EvoSprig runtime.
