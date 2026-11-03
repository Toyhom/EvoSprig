# CoworkOS, built with EvoSprig

![Cowork workflow in EvoSprig Studio](canvas.png)

An EvoSprig reproduction of [CoworkOS](https://github.com/RUC-NLPIR/CoworkOS): give a team a task, work together on shared documents, and pick up where you left off.

## A launch pack in one workspace

> Prepare a four-week pilot launch: analyze the budget and customer funnel, make the schedule, and draft the invitation.

![The team workspace and its finished documents](assets/workspace.png)

![A customer invitation drafted by the team](assets/document.png)

The team turns the brief into a budget analysis, launch plan, customer email and final decision brief. You can edit any document, inspect earlier revisions and download the result. A scheduled follow-up reads the latest edits before recommending the next actions.

## Try it

Set `DEEPSEEK_API_KEY`, then open the workbench:

```bash
evosprig serve --project examples/cowork/agent.yaml \
  --studio-dir apps/cowork --workspace .evosprig/cowork
```

Open **http://127.0.0.1:18766**, paste your request and start the team. The [sample brief](request.json) includes a pilot budget, customer funnel, owners and dates. Review or edit the final brief, then choose **Save and continue**.

For the workflow editor, replace `--studio-dir apps/cowork` with `--studio-dir apps/studio/dist`.

## Make it your team

- **Main agent:** plans specialist assignments and assembles their work.
- **Coordinator:** maps assignments to checkpointed subflows with bounded concurrency.
- **Specialists:** use shared documents and project memory, then save their deliverables.
- **Shared workspace:** people and agents edit through the same revision checks.
- **Follow-up:** a persisted wake-up resumes the task and reads the latest documents.

Edit the roles and prompts in [build_agent.py](build_agent.py). Attach your own tools, or replace the supplied request with a project brief. Select `plan`, `specialist` and `collaboration` in **Improve** to optimize the team's instructions against your tasks.

[Shared document API](../../docs/shared-workspaces.md) · [Build applications](../../docs/build-applications.md) · [Original CoworkOS](https://github.com/RUC-NLPIR/CoworkOS)
