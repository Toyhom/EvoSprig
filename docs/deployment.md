# Self-hosting and application deployment

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

The workspace contains project, run, memory, deletion-ledger, study and version databases. Keep SQLite on a filesystem that supports random writes and locks. Store large media artifacts in your chosen object store.

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
