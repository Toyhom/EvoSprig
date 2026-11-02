# Decision room

Explore a decision from both sides. Two agents present arguments, respond to each other and hand their disagreements to a moderator who writes a practical decision brief.

**Parallel opening arguments → parallel rebuttals → moderated recommendation**

## Try it

Configure a model as described in the [quickstart](../../docs/quickstart.md), then run:

```bash
evosprig run examples/debate/agent.yaml \
  --input-file examples/debate/sample.json
```

Open the application in Studio:

```bash
evosprig serve --project examples/debate/agent.yaml \
  --studio-dir apps/studio/dist
```

## Make it yours

Edit `sample.json` for your own task and the files under `prompts/` for the roles and instructions. All coordination, tool calls and parallel work use EvoSprig's AgentSpec and runtime. The [catalog builder](../build_catalog.py) shows how to create the same workflow with the Python SDK.

Use the [evolution guide](../../docs/evolution.md) to improve selected prompts on your own tasks. [Before and after](results/README.md) shows outputs from a fixed set of application tasks.

Application pattern inspired by [MetaGPT’s debate example](https://github.com/FoundationAgents/MetaGPT); implemented with EvoSprig's own framework.
