# Preload local models

Keep model servers alive across runs, node debugging and exported applications. The deployment owns the service; finishing an agent run leaves it loaded.

Add a `services` section to your deployment profile:

```yaml
models:
  main:
    base_url: http://127.0.0.1:8000/v1
    model: your-local-model
    api_key_env: LOCAL_MODEL_API_KEY
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

Set `LOCAL_MODEL_API_KEY` to the key configured on your local server. Use the appropriate environment's executable in `command`; arguments are passed directly, without a shell. Relative `cwd` values resolve from the profile directory. Start GPU services within your machine's assigned GPU allocation.

```bash
evosprig services start --profile deployment.yaml
evosprig services status --profile deployment.yaml
evosprig run agent.yaml --profile deployment.yaml --input-file task.json
evosprig services stop --profile deployment.yaml --name director
```

`run` and `serve` prepare configured services automatically. Set `autostart: false` for a service you preload manually. In Studio, open **Settings → Local models & tools** to check readiness or preload a configured service.

With the Python SDK, call `prepare_services("deployment.yaml")` from `evosprig.local_services` before constructing the runtime. Repeated calls reuse ready services. For an authenticated health or warmup endpoint, set the service's `auth_env` to the name of its bearer-token environment variable.

Readiness has two stages: the HTTP endpoint must respond, then each field in `ready` must match the health response. A warmup endpoint may enqueue loading; EvoSprig waits for the readiness fields. Use health fields that report loaded weights, rather than only a listening port. The media service's `loaded` field identifies the resident model family. Its default `idle_unload_seconds: 0` retains that family. For concurrent image, video and voice families, deploy separate service processes on suitable devices; one media worker switches families when asked to load another.

Services share a registry beside the profile at `.evosprig-services`. Concurrent starts using the same profile reuse one process and one warmup. New runs and server restarts reconnect. Logs remain in the registry for startup diagnosis. Explicit `stop` terminates only a process started by that registry, after checking its process identity. Existing endpoints are reused and remain under their operator's control. Use one shared profile directory when several applications should share a model.

The same support is bundled in Python, HTTP and container exports. In a Python export, run `python -m evosprig.local_services services start --profile deployment.yaml`; `app.py --profile deployment.yaml` also prepares services. Keep deployment commands and model paths in your own profile when moving the application to another machine.

For Episode Studio's complete model download and startup flow, use its [application launcher](../apps/episode-studio/README.md). A ComfyUI server becoming reachable does not load every checkpoint: use a model-loading warmup graph for the chosen recipe, or retain the cache after its first render.
