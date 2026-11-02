# Content studio

![Workflow in EvoSprig Studio](canvas.png)

Turn one source into an email, a social post and a product article. A shared fact sheet feeds a map subflow for each channel, followed by an editorial pass.

## One announcement, several channels

![Email and social copy produced from the same maintenance announcement](assets/result.png)

The selected version turns a hosting-maintenance notice into email and social copy while preserving the date, UTC window and service impact. Its writing team shares `brand_voice` and `source_fidelity` skills, which can evolve independently of the workflow.

## Run it

Set `DEEPSEEK_API_KEY`, or use a [deployment profile](../../docs/deployment.md) for your own model. Open the application in Studio:

```bash
evosprig serve --project examples/content-studio/agent.yaml \
  --studio-dir apps/studio/dist
```

Choose **Live model** and paste the input from `sample.json`. The final copy appears after all channel drafts have passed through the editor.

## Make it yours

Set the source, audience and channel list in `sample.json`. `brand_voice` and `source_fidelity` are shared skills used by the channel writers and editor. The native map node creates one task per channel.

In **Improve**, add your task inputs, select prompt or skill resources, and choose an algorithm. EvoSprig runs the same workflow with each candidate. [Agent configuration](../../docs/agent-resources.md) describes resource selection and model parameters.

Built with EvoSprig's [Python SDK](../build_work_apps.py). Application patterns draw on [Coze community content workflows](https://github.com/AICoderTudou/coze-workflows/tree/main/coze).
