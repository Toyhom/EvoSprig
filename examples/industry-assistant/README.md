# Industry assistant

![Workflow in EvoSprig Studio](canvas.png)

Build an agent that follows operating procedures, discovers business tools and completes tasks in an isolated industry environment. Evaluate its actual business outcomes, then improve its instructions against the same checks.

## Try it

Connect your IndustryBench installation and model as described in [industry environments](../../docs/industry-environments.md), then prepare a project with its own task split:

```bash
evosprig industry prepare --industry government --limit 12 --out my-industry-agent
evosprig evaluate my-industry-agent/agent.yaml \
  --suite my-industry-agent/suite.yaml --profile my-industry-agent/deployment.yaml
```

Choose `finance`, `government` or `manufacturing`. The environment supplies the public case, SOP and tool schemas; it keeps reference answers in its evaluator.

## Make it yours

Edit `prompts/procedure.md`, choose representative cases and tune the budgets in the generated deployment profile. Use `evosprig improve` with `--resource procedure` to search better operating instructions. All coordination uses EvoSprig's normal tool and agent nodes; evaluation sessions provide the business tools.
