# Preload local models

[English](local-models.md) · [简体中文](zh-CN/local-models.md) · [Documentation](README.md)

Keep model servers alive across runs, node debugging and exported applications. The deployment owns the service; finishing an agent run leaves it loaded.

Add a `services` section to your deployment profile:

```yaml
models:
  main:
    base_url: http://127.0.0.1:8000/v1
    model: your-local-model
    api_key_env: null
    local_service: director
services:
  director:
    command: [vllm, serve, /models/your-local-model, --port, '8000']
    health_url: http://127.0.0.1:8000/v1/models
    timeout_seconds: 3600
    retention: persistent
  images:
    health_url: http://127.0.0.1:18880/health
    warmup_url: http://127.0.0.1:18880/warmup
    warmup_body: {family: image}
    ready: {loaded: image}
    retention: persistent
```

The example uses an unauthenticated loopback server. For an authenticated server, set `api_key_env: LOCAL_MODEL_API_KEY` and provide that variable in the environment. Use the appropriate environment's executable in `command`; arguments are passed directly, without a shell. Relative `cwd` values resolve from the profile directory. Start GPU services within your machine's assigned GPU allocation.

```bash
evosprig services start --profile deployment.yaml
evosprig services status --profile deployment.yaml
evosprig run agent.yaml --profile deployment.yaml --input-file task.json
evosprig services stop --profile deployment.yaml --name director
```

`run` and `serve` prepare configured services automatically. Set `autostart: false` for a service you preload manually. In Studio, open **Local models & tools** to check readiness or preload a configured service.

With the Python SDK, call `prepare_services("deployment.yaml")` from `evosprig.local_services` before constructing the runtime. Repeated calls reuse ready services. For an authenticated health or warmup endpoint, set the service's `auth_env` to the name of its bearer-token environment variable.

Readiness has two stages: the HTTP endpoint must respond, then each field in `ready` must match the health response. A warmup endpoint may enqueue loading; EvoSprig waits for the readiness fields. Use health fields that report loaded weights, rather than only a listening port. The media service's `loaded` field identifies the resident model family. Its default `idle_unload_seconds: 0` retains that family. For concurrent image, video and voice families, deploy separate service processes on suitable devices; one media worker switches families when asked to load another.

Services share a registry beside the profile at `.evosprig-services`. Concurrent starts using the same profile reuse one process and one warmup. New runs and server restarts reconnect. Logs remain in the registry for startup diagnosis. Explicit `stop` terminates only a process started by that registry, after checking its process identity. Existing endpoints are reused and remain under their operator's control. Use one shared profile directory when several applications should share a model.

The same support is bundled in Python, HTTP and container exports. In a Python export, run `python -m evosprig.local_services services start --profile deployment.yaml`; `app.py --profile deployment.yaml` also prepares services. Keep deployment commands and model paths in your own profile when moving the application to another machine.

For Episode Studio's complete model download and startup flow, use its [application launcher](../apps/episode-studio/README.md). A ComfyUI server becoming reachable does not load every checkpoint: use a model-loading warmup graph for the chosen recipe, or retain the cache after its first render.

## Different models on different GPUs

A node selects a model alias; the alias points to a deployment connection; `local_service` points to the process to preload. Each process has its own `gpu_devices` list. Multiple nodes can share the same connection and resident weights.

```yaml
models:
  writing-api:
    base_url: http://127.0.0.1:8000/v1
    model: your-text-model
    api_key_env: null
    local_service: writer
  local-vision:
    base_url: http://127.0.0.1:8001/v1
    model: your-vision-model
    api_key_env: null
    capabilities: [text, structured_output, vision]
    local_service: reviewer
services:
  writer:
    command: [vllm, serve, /models/text, --port, '8000']
    health_url: http://127.0.0.1:8000/v1/models
    gpu_devices: [0]
    retention: persistent
  reviewer:
    command: [vllm, serve, /models/vision, --port, '8001']
    health_url: http://127.0.0.1:8001/v1/models
    gpu_devices: [1]
    retention: persistent
```

With `CUDA_VISIBLE_DEVICES=3,7`, `[0]` selects physical GPU 3 and `[1]` selects physical GPU 7. Values are **positions inside the current allocation**. With no `CUDA_VISIBLE_DEVICES`, they are physical indices. Omit `gpu_devices` to inherit the allocation; an out-of-range position is rejected.

For one model across two GPUs, set `gpu_devices: [0, 1]` and configure the serving engine's tensor parallelism, for example `--tensor-parallel-size 2` with vLLM. Device visibility alone does not shard weights. Install a serving-engine version that supports your model and provision enough VRAM for weights, cache and concurrent requests.

In Studio, use **Local models & tools → GPUs → Save placement → Preload**. Stop a managed service before changing its placement; then preload it again. A server already running outside this manager keeps its existing placement. Service status shows the resolved `CUDA_VISIBLE_DEVICES` for managed processes.

## Service configuration reference

| Field | Default | Purpose |
| --- | --- | --- |
| `health_url` | required | Loopback HTTP endpoint returning a JSON object |
| `command` | `[]` | Executable and arguments; empty means connect to an existing server |
| `cwd` | `.` | Working directory, relative to the profile |
| `gpu_devices` | omitted | GPU positions to expose to the child process |
| `warmup_url`, `warmup_body` | omitted, `{}` | Optional HTTP POST that starts model loading |
| `ready` | `{}` | Top-level health fields that must match; required with warmup |
| `auth_env` | omitted | Bearer-token environment variable for health/warmup requests |
| `timeout_seconds` | `1800` | Startup and readiness deadline, maximum 7200 |
| `poll_seconds` | `2` | Readiness polling interval, maximum 60 |
| `autostart` | `true` | Prepare this service when starting run/serve |
| `retention` | `persistent` | Retain until explicitly stopped or the host allocation ends |

The manager selects devices for local child processes. Cluster scheduling and remote servers remain managed by your deployment environment. Use [model connections](model-connections.md) to bind remote endpoints to nodes.
