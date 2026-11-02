# Book studio

![Workflow in EvoSprig Studio](canvas.png)

Turn an idea into a short guide. Plan a shared outline, write chapters in parallel and review consistency across the finished manuscript.

**Brief → outline → parallel chapter writers → editorial handoff**

<img src="assets/comparison.png" alt="Original and evolved chapters for the same community-event brief" width="100%" />

## What evolution changed

APE revised the outline and chapter prompts to preserve shared constraints and separate chapter responsibilities. In the original community-event guide, different chapters assign different amounts to the same budget items. The selected chapter follows the shared allocation and keeps coordination free.

The mean judge score was **0.740 → 0.895** across two held-out writing tasks, with DeepSeek Flash generating and judging. This folder contains the selected prompts.

### Improve your own writing team

Open **Improve** in Studio, add your writing briefs as task inputs, select `outline` and `chapter`, and choose APE. EvoSprig proposes edits, runs the workflow and compares the versions. You can also select a reusable skill attached to a writer, such as a style guide or editing checklist. Review the changes and enable the version you want to use.

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

Use the [evolution guide](../../docs/evolution.md) to improve selected prompts and skills on your own tasks.

Application pattern inspired by [CrewAI’s book-writing workflow](https://github.com/crewAIInc/crewAI-examples); implemented with EvoSprig's own framework.
