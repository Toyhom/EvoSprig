<div align="center">

<img src="docs/assets/hero.svg" alt="EvoSprig — Build agents that grow" width="880" />

**Build agents. Improve them with evidence. Ship them anywhere.**

[![CI](https://github.com/Toyhom/EvoSprig/actions/workflows/ci.yml/badge.svg)](https://github.com/Toyhom/EvoSprig/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**English** · [简体中文](README.zh-CN.md)

[Quickstart](docs/quickstart.md) · [Examples](examples/README.md) · [Evolution](docs/evolution.md) · [Documentation](docs/README.md)

</div>

EvoSprig brings visual workflows, persistent memory and evaluation-driven improvement into one agent development platform. Build with Python or Studio, compare candidate versions on your tasks, and export a standalone application.

<img src="docs/assets/studio.png" alt="EvoSprig Studio: workflow canvas, node settings and execution history" width="100%" />

## What you can build

| Application | Explore the workflow |
| --- | --- |
| **[Video production studio](examples/video-studio/)** | A VideoClaw-style pipeline: script → character assets → parallel shots → frame approval → video jobs → editing → composition. Retake one shot and keep the rest. |
| **[Research team](examples/research-team/)** | Retrieve evidence, run analyst and critic roles in parallel, then write and review a cited brief. |
| **[Customer support](examples/customer-support/)** | Look up an order, propose an action, require human approval and execute an idempotent refund. |
| **[Personal assistant](examples/personal-memory/)** | Remember preferences across sessions and answer with current facts, named context blocks and relationship history. |
| **[Evolving research assistant](examples/research-assistant/)** | Run tool-backed tasks, optimize instructions and compare candidates before enabling a new version. |

See the **[example gallery](examples/README.md)** for setup, runnable demos and integration guides. Video tools use a provider-neutral job contract; the included simulator exercises orchestration without generating media.

## Why EvoSprig?

- **Build in code or on a canvas.** Python Builder and Studio share one typed AgentSpec. Branch, loop, run parallel agents and pause for human input.
- **Make improvement measurable.** OPRO, GEPA, EvoPrompt GA/DE, Self-Refine and ACE produce versioned resource changes with evaluation reports, lineage and budgets.
- **Give agents useful memory.** BM25 retrieval, pluggable semantic search, named context blocks and temporal relationships preserve sources and user scope.
- **Resume real work.** Checkpoints, external job IDs and idempotency keys preserve progress across restarts and approvals.
- **Own the result.** Export Python source, an HTTP application or a container build project. The exported application runs independently of Studio.
- **Bring your tools and models.** Connect compatible model APIs, Python tools, HTTP services and MCP servers.

## Get started

Requires **Python 3.12+**. Studio also requires **Node.js 20+**.

```bash
git clone https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python -m pip install -e '.[server,evolution,mcp]'

# Run your first workflow without an API key.
evosprig run examples/hello/agent.yaml --input '{"question":"Hello"}' --mock

# Open Studio.
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --project examples/hello/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig
```

Open **http://127.0.0.1:18766**. Studio starts in English; switch to **中文** in the sidebar. Your language preference is saved in the browser.

For live models, configure environment-based credentials in a [deployment profile](examples/deployment.example.yaml). Follow the [quickstart](docs/quickstart.md) for model connections and export.

## Improve an agent

Choose a task suite and the resources the optimizer may edit:

```bash
evosprig improve examples/research-assistant/agent.yaml \
  --suite examples/research-assistant/suite.yaml \
  --method self_refine --resource instructions --rounds 3 \
  --profile examples/deployment.example.yaml --workspace .evosprig
```

Each study separates search, selection, release validation and test reporting. Inspect the diff and scores in Studio, then enable or roll back a version. See [method details and configuration](docs/evolution.md).

## Documentation

[Workflows and architecture](docs/architecture.md) · [Memory](docs/memory.md) · [Tools and MCP](docs/tools.md) · [Durable execution](docs/durable-runtime.md) · [Deployment](docs/deployment.md) · [Roadmap](docs/roadmap.md)

## Contributing

Bug reports, example applications and integrations are welcome. Read the [contributing guide](CONTRIBUTING.md) to run checks and submit a change.

## License

[Apache-2.0](LICENSE).
