# Supported capabilities

| Area | Available |
| --- | --- |
| Authoring | Python Builder, YAML/JSON AgentSpec 0.1/0.2/0.3, Studio canvas |
| Execution | Model/tool/agent nodes, conditions, joins, bounded loops, parallel branches, dynamic map, human approvals |
| Persistence | SQLite checkpoints, lease fencing, external jobs, cancellation and operation reconciliation |
| Models | OpenAI-compatible text, structured output, tools and streaming adapter |
| Tools | Python, JSON HTTP, asynchronous HTTP jobs, MCP Streamable HTTP, read-only SQLite; optional Python/WASM, browser and OCR tools |
| Memory | BM25, pluggable embeddings with rank fusion, context blocks, temporal relations, episodic/linked recall, source-aware summaries, multi-query retrieval, scoped deletion |
| Evolution | 13 training-free strategies across 11 families; [method matrix](evolution.md) |
| Evaluation | Search/selection/release/test partitions; rules, JSON schema, LLM-as-judge, external/composite scorers; output/node/trajectory/environment targets |
| Versions | Candidate diffs, lineage, manual release, rollback and snapshot export |
| Studio | English by default, persistent Chinese language option, workflow/resources/history/memory/improvement/releases |
| Delivery | Python source, standalone HTTP service, container build project, validated ZIP import |
| Examples | Data analysis, document chat, research team, video production, customer support, personal memory, software teams, Python analysis, debate, receipts, meetings, books, travel and motion graphics |

The default server uses SQLite and bounded asynchronous workers on one host. Container exports include a Dockerfile; build it with an OCI-compatible tool on your deployment host. Native TypeScript execution and multi-node platform deployment are on the [roadmap](roadmap.md).

Video production connects image/video services through a provider-neutral job contract. Task-specific agent quality depends on the configured model, tools and data.
