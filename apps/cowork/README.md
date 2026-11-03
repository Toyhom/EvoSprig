# Cowork workbench

A shared workspace for the [CoworkOS reproduction](../../examples/cowork/): launch a team task, review its brief, edit documents, browse revisions and download deliverables.

```bash
evosprig serve --project examples/cowork/agent.yaml \
  --studio-dir apps/cowork --workspace .evosprig/cowork
```

Open `http://127.0.0.1:18766`. Set `DEEPSEEK_API_KEY` before starting, or supply a deployment profile with `--profile`. The workbench uses the standard EvoSprig project/run APIs and [shared document API](../../docs/shared-workspaces.md).

Choose a follow-up delay when submitting a task. After you review the brief, the run saves its documents and schedules the next action check. Keep the server running or restart it with the same workspace to process pending work.
