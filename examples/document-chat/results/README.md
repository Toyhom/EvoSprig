# Chat with your documents — before and after

Compare the answers and handbook citations, including what the documents do not establish.

**New version selected.**

DeepSeek Flash runs the application and scores it against a fixed task rubric. These small examples illustrate behavior, not a benchmark or a guarantee of improvement.

## Try the evolved candidate

On 1 selection task, the original scored **0.950** and the strongest tested candidate scored **1.000**. Selection tasks help choose a version; they are not held-out results.

[Original snapshot](versions/baseline/agent.yaml) · [Candidate snapshot](versions/candidate/agent.yaml) · [Inputs, rubric and outputs](selection.json)

- Task 1: [original output](selection-1-baseline.md) · [candidate output](selection-1-evolved.md)

## On new tasks

On **2 held-out tasks**, the original scored **0.965** and the selected version **0.975**.

[Selected snapshot](versions/selected/agent.yaml) · [Inputs, rubric and outputs](release.json)

- Task 1: [original output](release-1-baseline.md) · [selected output](release-1-evolved.md)
- Task 2: [original output](release-2-baseline.md) · [selected output](release-2-evolved.md)

## Use the versions

Each snapshot contains its AgentSpec and prompt resources. Run it with the model and tool setup described in the [application guide](../README.md). The application in the parent folder may include later runtime settings; the snapshots preserve the compared versions.

```bash
evosprig run examples/document-chat/results/versions/baseline/agent.yaml \
  --input-file your-task.json
```

Replace `baseline` with `candidate` or `selected` where available. Use your own representative tasks and review outputs before adopting a resource change.
