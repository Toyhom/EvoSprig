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

## Real smoke record

On 2026-11-02, `scripts/live_evolution.py` ran OPRO and official GEPA 0.1.4 against
`deepseek-flash` using the same original version and fixed suite. It also evaluated
a separately authored manual prompt. The suite has 3 search, 2 selection, 2 release
validation and 2 sealed test cases; each validation/test split has one evidence
question and one addition task. Scores require exact normalized strings and, for
arithmetic, a completed addition-tool receipt.

| Configuration | Release validation | Sealed test |
| --- | --- | --- |
| Original prompt | 1/2 | 2/2 |
| Manual prompt | 2/2 | 2/2 |
| OPRO candidate | 2/2 | 2/2 |
| GEPA candidate | 2/2 | 2/2 |

The methods produced valid candidates and improved the release-validation formatting
score. The sealed test showed no gain, and the manual prompt matched both optimized
versions with shorter inputs. Two examples per held-out split cannot establish
statistical or general effectiveness. These are authored integration cases, not a
research benchmark claim.

The complete run used 70 model calls, 50,442 input tokens and 2,134 output tokens,
including search, reflection, paired validation and the manual baseline. All calls
returned usage; monetary billing is unknown. Per-method budgets and usage are in
[results/deepseek-smoke.json](results/deepseek-smoke.json), with the selected prompt
texts beside it. Private databases, credentials and raw operational logs are excluded.
