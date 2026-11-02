# Supported capabilities

| Area | Available |
| --- | --- |
| Authoring | Python Builder, YAML/JSON AgentSpec 0.1/0.2, Studio canvas |
| Execution | Model/tool/agent nodes, conditions, joins, bounded loops, parallel branches, human approvals |
| Persistence | SQLite checkpoints, lease fencing, external jobs, cancellation and operation reconciliation |
| Models | OpenAI-compatible text, structured output, tools and streaming adapter |
| Tools | Python, JSON HTTP, asynchronous HTTP jobs, MCP Streamable HTTP |
| Memory | BM25, pluggable embeddings with rank fusion, context blocks, temporal relations, citations, scoped deletion |
| Evolution | OPRO, official GEPA adapter, native EvoPrompt GA/DE, Self-Refine, ACE |
| Evaluation | Search/selection/release/test partitions; exact, contains and tool receipt metrics |
| Versions | Candidate diffs, lineage, manual release, rollback and snapshot export |
| Studio | English by default, persistent Chinese language option, workflow/resources/history/memory/improvement/releases |
| Delivery | Python source, standalone HTTP service, container build project, validated ZIP import |
| Examples | Video production, research team, customer support, personal memory, prompt optimization and motion graphics |

The default server uses SQLite and bounded asynchronous workers on one host. Container exports include a Dockerfile; build it with an OCI-compatible tool on your deployment host. Native TypeScript execution and multi-node platform deployment are on the [roadmap](roadmap.md).

The video example validates the production workflow through a deterministic job simulator. Connect media providers through its documented service contract. Search method tests validate their mechanics and shared runtime integration; task-specific performance should be measured on your own evaluation suite.
