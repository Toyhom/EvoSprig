# Open-source scope

EvoSprig is licensed under Apache-2.0. The public repository contains:

- The SDK, runtime, model/tool adapters, memory and evolution modules, Studio and exporters.
- User documentation, schemas, tests, dependency locks and CI/release tooling.
- Original example applications, redistributable prompt templates and curated, de-identified validation summaries.

The public tree excludes internal planning and agent instructions, development conversations, private research, credentials, deployment-specific configuration, raw operational logs, user databases, private memories, caches, environments, model weights and third-party reference screenshots. Those materials are not required to build or self-host the product. Local generated applications and runtime data remain in their configured workspaces.

Directory separation is the primary boundary. Ignore files and release allowlists provide additional checks. Before publishing source or packages, run:

```bash
python scripts/release/audit.py --git-history
python scripts/release/audit.py --artifacts dist
```

The audit checks the source allowlist, all reachable Git commits and annotated tags, deleted historical files, links, runtime artifacts, credential patterns and private deployment references. It reports paths and rule names without echoing matching secrets. Automated checks complement review of data ownership, licensing and publication intent.

Third-party dependencies are installed separately; attribution is recorded in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). The repository does not redistribute model weights, FFmpeg binaries or third-party media assets.
