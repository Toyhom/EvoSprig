# Book studio

Turn an idea into a short guide. Plan a shared outline, write chapters in parallel and review consistency across the finished manuscript.

**Brief → outline → parallel chapter writers → editorial handoff**

<img src="results/comparison.png" alt="Original and evolved chapters for the same community-event brief" width="100%" />

## Try it

Configure a model as described in the [quickstart](../../docs/quickstart.md), then run:

```bash
evosprig run examples/book-studio/agent.yaml \
  --input-file examples/book-studio/sample.json
```

Open the application in Studio:

```bash
evosprig serve --project examples/book-studio/agent.yaml \
  --studio-dir apps/studio/dist
```

## Make it yours

Edit `sample.json` for your own task and the files under `prompts/` for the roles and instructions. All coordination, tool calls and parallel work use EvoSprig's AgentSpec and runtime. The [catalog builder](../build_catalog.py) shows how to create the same workflow with the Python SDK.

Use the [evolution guide](../../docs/evolution.md) to improve selected prompts on your own tasks. [Before and after](results/README.md) shows outputs from a fixed set of application tasks.

Application pattern inspired by [CrewAI’s book-writing workflow](https://github.com/crewAIInc/crewAI-examples); implemented with EvoSprig's own framework.
