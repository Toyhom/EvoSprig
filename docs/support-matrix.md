# Supported capabilities

| Area | Available |
| --- | --- |
| Authoring | Python Builder, YAML/JSON AgentSpec 0.1/0.2/0.3, Studio canvas, nested visual groups and subflow editor |
| Execution | Model/tool/agent/code nodes, conditions, joins, bounded loops, parallel branches, dynamic map, human approvals |
| Persistence | SQLite checkpoints, lease fencing, deduplicated event intake, external jobs, cancellation and operation reconciliation |
| Models | OpenAI-compatible text, image inputs, structured output, tools and streaming; per-node temperature, top-p and output limits |
| Agent resources | Main prompts and ordered reusable skills; independent resource search and shared-resource editing |
| Tools | Python, JSON HTTP, asynchronous HTTP jobs, MCP Streamable HTTP, read-only SQLite, ComfyUI graphs and Git worktrees; optional Python/WASM, browser, OCR and local image/video generation tools |
| Memory | BM25, pluggable embeddings with rank fusion, context blocks, temporal relations, episodic/linked recall, source-aware summaries, multi-query retrieval, scoped deletion |
| Shared workspace | Revisioned documents, peer mailboxes, direct agent messages, resumable waits and durable wake-ups |
| Evolution | 23 training-free strategies across 21 families; prompts, skills, harness parameters, graphs, code, routing and memory search; custom optimizer registration; [method matrix](evolution.md) |
| Evaluation | Search/selection/release/test partitions; rules, JSON schema, LLM-as-judge, external/composite scorers; output/node/trajectory/environment targets, concurrent isolated samples, IndustryBench replay |
| Versions | Candidate diffs, lineage, manual release, rollback and snapshot export |
| Studio | English and Chinese, nested canvas, selected-node/group debugging with saved execution inputs, resources, history, memory, improvement and releases |
| Delivery | Python source, standalone HTTP service, container build project, validated ZIP import |
| Examples | Episode Studio, Super-agent repository maintenance, VideoClaw production, CoworkOS office teams, robot manipulation, data analysis, document chat, research, customer support, personal memory, software teams, Python analysis, debate, receipts, meetings, books, travel, career coaching, content campaigns, interactive learning, motion graphics, industry assistants and environment drafting |

The default server uses SQLite and bounded asynchronous workers on one host. Container exports include a Dockerfile; build it with an OCI-compatible tool on your deployment host. Native TypeScript execution and multi-node platform deployment are on the [roadmap](roadmap.md).

Video production connects image/video services through a shared job contract. The optional [local worker](../apps/media-service/) provides image generation, reference conditioning, audio/transcript inspection and film assembly. [ComfyUI recipes](comfyui.md) expose model and adapter controls; [vision nodes](vision.md) review generated frames and clips.
