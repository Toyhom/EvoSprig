# Improve an agent on your own tasks

[English](improve-an-agent.md) · [简体中文](../zh-CN/tutorials/improve-an-agent.md) · [Learning path](README.md)

**Goal:** give an existing agent representative tasks, search a small change and compare the resulting versions.

Use a text application such as [Xiaohongshu Studio](../../examples/xiaohongshu-studio/) for a first iteration. Its short runs make it easy to inspect a prompt or skill change. Configure and open it using its example guide.

## 1. Make a small task set

Write tasks from actual work: introduce a product, explain a feature to a beginner, or turn supplied notes into a short post. Include the source facts, audience and desired result. Put different tasks into search, selection, release and test partitions. Keep at least one failure case, such as a draft that confuses video duration with generation time.

In **Improve**, choose an input-task suite with an LLM judge, or supply reference outputs and business checks. The [evaluation reference](../evaluation.md) contains complete suite formats and judge configuration.

Use the included [eight introductory tasks](writing-tasks.jsonl) for the first run, then replace them with your own inputs. After the example's setup command, run from the repository root:

```bash
evosprig suite --inputs docs/tutorials/writing-tasks.jsonl \
  --name writing-intro --out .evosprig/writing-tasks.yaml \
  --rubric "Use only supplied facts; distinguish film length from generation time; explain a concrete use; preserve required names and links."
evosprig improve examples/xiaohongshu-studio/agent.yaml \
  --suite .evosprig/writing-tasks.yaml --method self_refine \
  --resource source_fidelity --rounds 1 --max-candidates 4 \
  --max-model-calls 200 --max-total-tokens 200000 --timeout 1800 \
  --workspace .evosprig/writing-study \
  --profile .evosprig/examples/xiaohongshu-studio/deployment.yaml
```

`suite` creates disjoint partitions; `improve` records the study ID and selected version. The included tasks check source fidelity and useful introductions. Model, proposal and judge calls all count toward the budget. A budget is a ceiling; inspect your provider's billing for cost.

## 2. Select what may change

Choose one prompt or skill, such as `source_fidelity`. Read it before starting. Keep tools, model connections and permissions fixed for the first experiment. Set a small proposal and model-call budget.

Select **Self-Refine** for a first feedback-driven revision. Other methods accept different feedback and search spaces; use the [method guide](../evolution.md) when choosing one for your application.

## 3. Run and inspect

Start the study. Inspect the candidate resource diff and the outputs on selection tasks. Look for the concrete behavior you asked to improve: factual claims, required details, output structure or task completion. Check that a stronger answer on one task did not break another.

## 4. Choose a version

To inspect a CLI run, copy its study ID into:

```bash
evosprig studies xiaohongshu-studio --workspace .evosprig/writing-study
evosprig compare xiaohongshu-studio --study STUDY_ID \
  --workspace .evosprig/writing-study --out .evosprig/writing-comparison.md
```

Open the comparison and inspect the actual resource edits and paired answers. Use the release tasks and your acceptance criteria before enabling a candidate. Existing runs retain their frozen version. Export the selected version when ready to deploy. Keep the separate test partition for the final check.

For Comic Studio, begin with screenplay and panel-plan tasks. Add image-based judging after the text contract is reliable. Image generation, vision review and retries should be included in the evaluation budget.

**Continue:** [evaluation schemas](../evaluation.md), [search spaces](../harness-search.md), [algorithm extensions](../optimizer-plugins.md).
