# Quickstart

[English](quickstart.md) · [简体中文](zh-CN/quickstart.md) · [Documentation](README.md)

Requires Python 3.12+. Building Studio also requires Node.js 20+.

## Install and run

```bash
git clone https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python -m pip install -e '.[server,evolution,mcp]'
evosprig validate examples/hello/agent.yaml
evosprig run examples/hello/agent.yaml --mock --input '{"question":"Hello EvoSprig"}'
```

The example calls a text-statistics tool, then passes the question and result to a model. `--mock` uses deterministic offline responses. Rebuild its specification from Python with `python examples/hello/build_agent.py`.

| Extra | Adds |
| --- | --- |
| `models` | Compatible model APIs |
| `server` | Local HTTP API and workers |
| `evolution` | Official GEPA library |
| `mcp` | MCP tool client |
| `media` | Motion-graphics renderer dependencies |
| `dev` | Development and test tools |

## Connect a model

Set `DEEPSEEK_API_KEY` in your shell or secret manager, then run:

```bash
evosprig run examples/hello/agent.yaml \
  --profile examples/deployment.example.yaml \
  --input '{"question":"What is 2 + 3?"}'
```

The example profile uses `https://api.deepseek.com` and `deepseek-flash`. For another compatible provider, change `base_url`, `model`, `api_key_env` and capabilities in your own profile. Keep credentials in environment variables. Local inference services can use loopback HTTP.

## Open Studio

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --workspace .evosprig/studio \
  --project examples/hello/agent.yaml --studio-dir apps/studio/dist
```

Open **http://127.0.0.1:18766**. Studio starts in English and offers a persistent Chinese language option in the sidebar.

1. Select a project or create one. Add nodes, connect their ports and edit their parameters.
2. Save the workflow and run it. Live mode uses the server's model profile and environment.
3. Edit prompts in **Resources**, inspect execution in **History**, and manage facts in **Memory**.
4. Import a task suite in **Improve**, choose editable resources, a method and a budget.
5. Compare candidates in **Versions**, then enable, roll back or export a version.

Unsaved changes are retained when a save fails. Studio prompts before replacing a draft. If another editor changed the revision, save returns a conflict; compare your local draft with the latest version before retrying.

For remote development, forward the loopback port through SSH. Use `--port` to choose another port, and `--token-env EVOSPRIG_API_TOKEN` to require an API token. [Deployment guide](deployment.md).

## Run an application

The [example gallery](../examples/README.md) includes video production, multi-agent research, approval-based support and persistent memory. Each example has a runnable entrypoint and explains its model/tool dependencies.

## Export an independent application

```bash
evosprig export examples/hello/agent.yaml --out .evosprig/exports/hello
cd .evosprig/exports/hello
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --mock --input '{"question":"Hello"}'
```

Use a separate Python environment for the exported application. The export contains AgentSpec, resources, readable Builder code, runtime source and dependency locks. Supply service credentials on the deployment host. HTTP and container targets add a standalone server; see [deployment](deployment.md).

## Development

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
ruff check src tests examples scripts
pytest -q
npm --prefix apps/studio test
```

Browser tests use a temporary API on port 18765. Set `EVOSPRIG_PYTHON` and `EVOSPRIG_TEST_WORKSPACE` when using a specific interpreter or workspace. For frontend hot reload, run `npm --prefix apps/studio run dev`; `EVOSPRIG_API_PORT` sets the backend proxy port.
