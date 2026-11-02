# Evidence and tool research assistant

This example answers from supplied evidence, retrieves uploaded project documents
through `documents.search`, and uses `builtin.add` for measured counts. Its model
output is a JSON object with an answer string. Prompt resources, Builder source,
AgentSpec and a fixed nine-case evaluation suite are included.

```bash
evosprig run examples/research-assistant/agent.yaml --mock \
  --input '{"question":"Which database is named?","evidence":"The runtime uses SQLite."}'
# Set DEEPSEEK_API_KEY in your terminal for real model calls; omit --mock.
evosprig improve examples/research-assistant/agent.yaml \
  --suite examples/research-assistant/suite.yaml --method opro \
  --resource instructions --rounds 1 --workspace ./research-workspace
evosprig improve examples/research-assistant/agent.yaml \
  --suite examples/research-assistant/suite.yaml --method gepa \
  --resource instructions --max-metric-calls 12 --workspace ./research-workspace
```

GEPA requires `pip install 'evosprig[evolution]'`. The CLI prints a persisted study
ID, candidate versions, validation gate and token usage. Use `evosprig versions
research-assistant --workspace ./research-workspace` to inspect the archive.
`export-version` exports a selected snapshot. Publishing is a separate manual action.

For document-backed answers, upload plain text in Studio's memory/documents view.
Document hits retain their source and exact offsets. A normal run sees the current
user's project documents. Evaluation samples start with empty private memory;
the included suite supplies its evidence explicitly so candidate comparisons are
reproducible and independent of a user's private document collection.

## Compare methods

Use `--method opro`, `gepa`, `evoprompt_ga`, `evoprompt_de`, `self_refine` or `ace` with the same suite. Keep model settings and budgets fixed when comparing runs. The included nine-case suite exercises integration and output contracts; extend it with representative tasks to measure performance on your application.

The `results/` directory includes selected prompt variants you can inspect or reuse. Method mechanics, population settings and playbook updates are documented in [Evolution](../../docs/evolution.md).
