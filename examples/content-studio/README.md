# Content studio

![Workflow in EvoSprig Studio](canvas.png)

Turn one source into an email, a social post and a product article. A shared fact sheet feeds a map subflow for each channel, followed by an editorial pass.

## One announcement, several channels

**Source:** North Museum opens until 8pm on April 2, 2027. Tickets are $12, or $7 for students with ID. The archive stays closed and the cafe closes at 6pm. Tickets are sold at the front desk.

The selected workflow produces a social post and an email. Both carry the date, prices and exceptions into the channel copy.

> **Subject:** North Museum open late on April 2, 2027

| Detail carried into the copy | Value |
| --- | --- |
| Late opening | Until 8pm on April 2, 2027 |
| Tickets | $12 standard; $7 students with ID |
| Purchase | Front desk only |
| Exceptions | Archive closed; cafe closes at 6pm |

### Shared skills across the writing team

`brand_voice` guides the channel writers and editor:

> Lead with the most useful information, such as what is happening, when, and who it affects. Use concrete verbs and specific nouns instead of vague or promotional wording.

`source_fidelity` keeps qualifiers, limits and dates attached to the claims they modify. Select either skill in **Improve** to search for a version suited to your own announcements.

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
