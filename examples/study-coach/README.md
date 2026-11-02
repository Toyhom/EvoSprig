# Study coach

![Workflow in EvoSprig Studio](canvas.png)

Learn a topic, try three application questions, then get feedback on your answers. The lesson can use saved learning preferences; a human node keeps the exercise interactive.

## Practice the idea, then review your answer

The agent asks about Python shallow copies:

```python
a = [[1], [2]]
b = a.copy()
b.append([7])
b[0].append(8)
# What is a now?
```

The learner answers `[[1, 8], [2], [7]]`. The feedback explains the distinction:

> A shallow copy does *not* share the outer list; it creates a new outer list. What's shared is the *inner* lists. So `b.append([7])` changes only `b` (new outer list), while `b[0].append(8)` mutates the shared inner list `[1]`, which `a` also references.

It gives the corrected value, `[[1, 8], [2]]`, and a follow-up exercise: does `b[1] = [99]` change `a`? The learner can apply the same distinction to a new case.

## Run it

Set `DEEPSEEK_API_KEY`, or use a [deployment profile](../../docs/deployment.md) for your own model. Open the application in Studio:

```bash
evosprig serve --project examples/study-coach/agent.yaml \
  --studio-dir apps/studio/dist
```

Choose **Live model** and paste the input from `sample.json`. Read the lesson and questions in **History**, then submit three strings in an `answers` array. The coach continues with question-by-question feedback.

## Make it yours

Replace the topic, level and teaching material in `sample.json`. Edit the `teaching` and `coaching_feedback` skills to match your course. Saved preferences are read from the current user and project memory.

For unattended improvement, import an [evaluation suite](../../docs/evaluation.md#bring-your-own-task-suite) with three learner answers in each task's `responses`: `{"graph/learner": {"answers": ["...", "...", "..."]}}`. Then select prompt or skill resources and an algorithm in **Improve**. EvoSprig runs the same workflow with each candidate. [Agent configuration](../../docs/agent-resources.md) describes resource selection and model parameters.

Built with EvoSprig's [Python SDK](../build_work_apps.py). Application patterns draw on [Coze community learning workflows](https://github.com/AICoderTudou/coze-workflows/tree/main/coze).
