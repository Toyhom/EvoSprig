# Self-hosting and application deployment

[English](deployment.md) · [简体中文](zh-CN/deployment.md) · [Documentation](README.md)

The platform provides editing, evaluation and version management. An exported application runs a selected version independently.

## Run the platform

```bash
python -m pip install -e '.[server,evolution,mcp]'
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --workspace ./state --project examples/hello/agent.yaml \
  --studio-dir apps/studio/dist --max-concurrent-runs 4
```

The server binds to `127.0.0.1:18766`; use SSH forwarding for remote access. `--profile deployment.yaml` supplies model/tool bindings. `--token-env EVOSPRIG_API_TOKEN` enables a workspace token. Enter the same token in Studio's Connection panel.

For separate user identities, supply `--auth-file principals.yaml`:

```yaml
- user: alice
  tenant: team
  token_env: EVOSPRIG_ALICE_TOKEN
- user: bob
  tenant: team
  token_env: EVOSPRIG_BOB_TOKEN
```

Tokens are resolved from the service environment. Projects, runs, memory and candidates belong to the authenticated principal. `--project` imports under the default local identity; authenticated users should create or import their own projects in Studio.

Use your process manager to restart the service. Durable runs resume from checkpoints; uncertain external writes follow the [reconciliation protocol](durable-runtime.md). The default deployment uses SQLite and bounded asynchronous workers on one host.

## Persistent state

The workspace contains project, run, memory, shared-document, deletion-ledger, study and version databases. Keep SQLite on a filesystem that supports random writes and locks. Store large media artifacts in your chosen object store.

Back up databases using SQLite's backup API or stop the platform while taking a consistent backup. Retain the newest deletion ledger during restore so deleted memory cannot reappear. Supply credentials again through the deployment environment.

## Export an application

```bash
evosprig export examples/hello/agent.yaml --target python --out ./hello-python
evosprig export examples/hello/agent.yaml --target http --out ./hello-http
evosprig export examples/hello/agent.yaml --target container --out ./hello-container
```

For HTTP/MCP/external tools, add `--profile deployment.yaml`. The export includes a behavior lock, dependency locks, runtime source, file hashes and an external-dependency report. Plugins without export support produce an incompatibility report.

Install and run the HTTP export in a separate Python 3.12 environment:

```bash
cd hello-http
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --mock --input '{"question":"Hello"}'
# Set EVOSPRIG_SERVICE_TOKEN, then:
python serve.py --mock --workspace ./state
```

The application service uses loopback port 8080. Business endpoints require `Authorization: Bearer <token>`. `POST /runs` accepts `{"input": {...}}`; run-specific routes expose status, events, human input and cancellation. `/health` returns availability and version.

Container exports include a Dockerfile, an unprivileged UID 10001 and a persistent `/state` directory. Build and run instructions are included in the exported README. Add a TLS reverse proxy and appropriate access controls for remote deployments.

## Import an exported project

```bash
evosprig import hello.zip
evosprig import hello.zip --out ./imported-project
```

Studio's Import Project action inspects the ZIP before creating a project. Imports validate paths, sizes, manifests, hashes and plugin references, then load declarative specs and resources. They do not execute archived Python. Rebuild version locks after editing exported source or resources.

## Adjustable execution defaults

A model node inherits `execution.max_output_tokens` (512 by default); set `max_output_tokens` on a model/agent node for a longer deliverable. Shared token and elapsed-time budgets still apply. `output_errors: feedback` asks the model to repair invalid JSON/schema output or truncation, with `max_output_retries: 1` by default and a maximum of three. The default policy is `raise`, so existing applications retain their behavior. Transport errors are not format errors.

This follows the bounded validation-feedback pattern used by [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output). Set output length to the task and provider limits; a repeated truncation can require a larger node limit, a smaller task or a more capable model.

Independent evaluation cases can run concurrently using `evaluation.environment.max_concurrent_samples` in the deployment profile (default 1, maximum 32). Each receives a fresh identity and environment. Results retain input order, all calls share the experiment budget, and assessment failures cancel remaining cases. Increase concurrency according to provider quotas and environment capacity. Ordinary serving separately exposes `--max-concurrent-runs` (default 4).

## Model HTTP connections

The OpenAI-compatible adapter reuses HTTP connections across nodes and concurrent runs in the same provider session. Evaluation keeps task and judge pools open for a batch; the last session closes the client, including on cancellation. Model bindings accept `max_connections` (default 32) and `max_keepalive_connections` (default 8, no larger than the total). These limit sockets, while workflow and evaluation concurrency settings control scheduled work.

For Qwen served by vLLM, set `json_mode: without_tools` in the model binding. This keeps the server's JSON grammar out of tool-call turns and enables it when no tools are offered. The runtime still validates every final answer against the node schema and applies its configured repair budget. The default `always` sends JSON mode on every JSON-output request; `off` leaves formatting to the model and runtime validation.

## Resident local models

Declare model and tool servers in your deployment profile, preload them once and reuse them across runs. Studio shows their readiness; exported applications use the same service manager. See [Preload local models](local-models.md).

## Bind models after delivery

Exports include a provider-neutral `model-contract.json` and `deployment.example.yaml`. The application operator can provision local inference or an API later, then bind it without changing the exported agent. Business clients submit tasks; provider credentials stay in the application deployment. See [application/model separation](model-connections.md#separate-applications-from-model-deployments).
