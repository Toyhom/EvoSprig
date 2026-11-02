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

## What will you build?

<img src="docs/assets/applications.png" alt="Applications built with EvoSprig: a generated web app, data charts, receipt processing and book writing" width="100%" />

| Build an agent that… | Start here |
| --- | --- |
| Turns a brief into a working web app | **[Software team](examples/software-team/)** — design, implementation, browser checks and repair |
| Runs Python and explains your data | **[Data Interpreter](examples/data-interpreter/)** — files, calculations and charts |
| Helps you make a difficult decision | **[Decision room](examples/debate/)** — opposing arguments, rebuttals and a moderated recommendation |
| Reads receipts and checks expenses | **[Receipt assistant](examples/receipt-assistant/)** — OCR, structured extraction and policy review |
| Researches a question with a team | **[Research team](examples/research-team/)** — parallel investigation, sources and editorial approval |
| Produces a video from an idea | **[Video studio](examples/video-studio/)** — scripts, approved shots, media tools and local retakes |
| Organizes the rest of your work | **[Meetings](examples/meeting-assistant/)** · **[Books](examples/book-studio/)** · **[Travel](examples/travel-planner/)** |

Also explore **[SQL analysis](examples/data-analyst/)**, **[document chat](examples/document-chat/)**, **[customer support](examples/customer-support/)** and **[personal memory](examples/personal-memory/)**. Every application uses EvoSprig's own SDK, AgentSpec and runtime. Open the **[gallery](examples/README.md)** for setup and before/after outputs.

## Why EvoSprig?

- **Controlled evolution.** 13 training-free strategies across 11 method families: prompt search, population search, demonstrations, reflections and experience playbooks. Choose the resources, budget and release criteria.
- **Evaluation that fits your application.** Start with task inputs and an LLM judge, or bring reference answers, business checks and a sandbox. Score outputs, steps, tools and environment outcomes.
- **Code and canvas, one application.** Build typed workflows with parallel agents, dynamic map, loops and human approvals. Edit the same version in Python or Studio.
- **Memory agents can use.** Scoped facts, hybrid retrieval, context blocks, temporal relations, linked experiences and source-aware summaries.
- **Tools for real work.** MCP, HTTP, SQL and Python plugins; optional code execution, browser checks and OCR; read-only concurrency and recoverable tool feedback.
- **Run, recover and ship.** Checkpoints and external job receipts preserve progress. Export standalone Python, HTTP applications or container build projects.

## How it fits together

<img src="docs/assets/architecture.svg" alt="EvoSprig architecture: authoring, AgentSpec, durable runtime, tools and memory, evaluation, controlled evolution and release" width="100%" />

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

## See what changes after evolution

The [application gallery](examples/README.md#before-and-after) pairs original outputs with the version retained after search on the same tasks. Open a comparison to read the outputs, try the candidate resources and see whether the search kept the original or selected a new version. The platform keeps the baseline when a proposal does not improve selection performance.

Bring your own inputs to **[LLM-as-judge](docs/evaluation.md)**, or connect your evaluator. The **[method guide](docs/evolution.md)** explains which feedback each strategy uses. Review the diff and outputs before enabling a version; a search never publishes itself.

## Documentation

[Workflows and architecture](docs/architecture.md) · [Memory](docs/memory.md) · [Tools and MCP](docs/tools.md) · [Durable execution](docs/durable-runtime.md) · [Deployment](docs/deployment.md) · [Roadmap](docs/roadmap.md)

## Contributing

Bug reports, example applications and integrations are welcome. Read the [contributing guide](CONTRIBUTING.md) to run checks and submit a change.

## License

[Apache-2.0](LICENSE).
