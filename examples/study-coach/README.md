# Study coach

![Workflow in EvoSprig Studio](canvas.png)

Learn a topic, try three application questions, then get feedback on your answers. The lesson can use saved learning preferences; a human node keeps the exercise interactive.

## Keep the lesson and feedback on the same problem

![Original answer, automatic skill edits and selected feedback](assets/evolution.png)

One Self-Refine round rewrote the `teaching` and `coaching_feedback` skills shared by the lesson, quiz and feedback nodes. The original exercise drifted away from the supplied problem; the selected version keeps its quantities and explains the learner’s mistakes against the source.

On two held-out teaching tasks, the paired output score was **0.55 → 0.86**, with DeepSeek Flash generating and judging. The judge receives the actual quiz and learner replies. The six input tasks were adapted from [GSM8K](https://huggingface.co/datasets/openai/gsm8k) (MIT), with incomplete learner responses. This folder contains the selected skills.

To improve your own tutor, add representative lessons and learner answers, select these skills in **Improve**, and choose Self-Refine. Inspect the edits and feedback before enabling the version.

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
