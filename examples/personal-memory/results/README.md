# Personal assistant — before and after

Compare how saved preferences inform the response and how explicitly requested updates are recorded.

**Original version retained.**

DeepSeek Flash runs the application and scores it against a fixed task rubric. These small examples illustrate behavior, not a benchmark or a guarantee of improvement.

## On new tasks

The retained original scored **0.950** on **2 held-out tasks**. The retained version is reported once; it has no evolution gain.

[Original snapshot](versions/baseline/agent.yaml) · [Inputs, rubric and outputs](release.json)

- Task 1: [original output](release-1-baseline.md)
- Task 2: [original output](release-2-baseline.md)

This search did not produce a distinct candidate with a completed selection result.

## Use the versions

Each snapshot contains its AgentSpec and prompt resources. Run it with the model and tool setup described in the [application guide](../README.md). The application in the parent folder may include later runtime settings; the snapshots preserve the compared versions.

```bash
evosprig run examples/personal-memory/results/versions/baseline/agent.yaml \
  --input-file your-task.json
```

Replace `baseline` with `candidate` or `selected` where available. Use your own representative tasks and review outputs before adopting a resource change.
