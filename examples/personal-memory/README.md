# Personal memory assistant

A persistent assistant combines named context blocks, retrieved facts and changing relationships. It adapts the managed-context and long-term-memory patterns found in [Letta](https://github.com/letta-ai/letta) and [Mem0](https://github.com/mem0ai/mem0) using EvoSprig's own scoped storage.

```bash
python examples/personal-memory/run_demo.py --workspace .evosprig/personal
# Reuse the workspace to retain the same profile across sessions.
python examples/personal-memory/run_demo.py --workspace .evosprig/personal
```

The example records that Alice moved from project Orion to Atlas. Current retrieval returns Atlas; a historical query at the earlier timestamp returns Orion. A profile block carries the user's preferred response style. Add `--live` for the configured model.

`memory.context`, `memory.search` and `memory.relations` are ordinary runtime tools. Their identity is bound by the deployment, so model arguments cannot select another user's records. Swap BM25 for `HybridMemory` with an embedding provider when semantic matching is needed. See [memory configuration](../../docs/memory.md).
