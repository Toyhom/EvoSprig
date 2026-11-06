# Default model and node overrides

[English](model-connections.md) · [简体中文](zh-CN/model-connections.md) · [Documentation](README.md)

Set one default connection for the application, then override individual nodes when they need a different model. Every model or agent node selects a **model binding**. Give a writer a text model, a visual reviewer a multimodal model, and a tool-using role a model with tool calls. Different bindings can use different vendors or local servers in the same application.

In Studio, open **Model connections** in the sidebar. Choose a provider address, enter its model ID and the name of its API-key environment variable, then save. Choose **Application default model** to set `main`. Select an agent and choose another connection under **Model** for a node-specific override. New model nodes use `main`; existing explicit aliases keep their selection. Enable image support only for a model that accepts images; select the node's image inputs separately.

| Connection | Base URL |
| --- | --- |
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com` |
| Kimi | `https://api.moonshot.cn/v1` |
| MiniMax | `https://api.minimax.io/v1` |
| Qwen / DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Local vLLM or another OpenAI-compatible server | e.g. `http://127.0.0.1:8000/v1` |

Use the model ID and regional endpoint provided by your account. Set credentials in the server's environment. Provider-specific reasoning and token options are documented in [vision and provider options](vision.md).

## Python: one default, optional overrides

Use a single variable for the common model. `default_model()` defines the `main` alias. Nodes that omit `model` inherit it, including nodes inside map, loop and parallel subflows. An explicit alias takes precedence.

```python
from evosprig.sdk import Builder

DEFAULT_MODEL = "writing-api"
builder = Builder("my-team", {"type": "object"}, {"type": "object"})
builder.default_model(DEFAULT_MODEL, ["text", "structured_output"])
builder.model("vision", "local-vision", ["text", "structured_output", "vision"])
builder.node("writer", "model", instructions="Write a concise scene.",
             inputs={}, output_schema={"type": "object"})
builder.node("reviewer", "model", model="vision", instructions="Review the scene.",
             inputs={"scene": {"ref": "nodes.writer.output"}},
             output_schema={"type": "object"})
builder.edge("writer", "reviewer")
builder.output(result={"ref": "nodes.reviewer.output"})
spec = builder.build_spec()
```

The saved AgentSpec contains explicit `model: main` references, so exports and the runtime use the same selection. For hand-written YAML, set `model: main` on nodes that share the default. Rebind `models.main.binding` to change their connection together.

For several explicit roles:

```python
builder.model("writer", "writing-api", ["text", "structured_output"])
builder.model("reviewer", "local-vision", ["text", "structured_output", "vision"])
# Set model="writer" or model="reviewer" on each node.
```

## Deployment connections

Configure these deployment connections in `deployment.yaml`:

```yaml
models:
  writing-api:
    base_url: https://your-provider.example/v1
    model: your-text-model
    api_key_env: WRITER_API_KEY
  local-vision:
    base_url: http://127.0.0.1:8000/v1
    model: your-vision-model
    api_key_env: null
    capabilities: [text, structured_output, vision]
    local_service: vision-server
services:
  vision-server:
    command: [vllm, serve, /models/your-vision-model, --port, '8000']
    health_url: http://127.0.0.1:8000/v1/models
    timeout_seconds: 3600
    retention: persistent
```

`local_service` associates a model connection with its resident service. **Preload** appears on nodes using it; runs and exported applications also prepare autostart services from their deployment profile. Multiple nodes using this connection share the loaded server. See [preloading and retention](local-models.md).

Start Studio with `--profile deployment.yaml` to edit these connections. Node-to-binding choices are versioned with the application; endpoints and credentials belong to deployment. In a server configured with multiple user identities, its operator maintains the shared connection file.

## Separate applications from model deployments

Application code declares **roles and capabilities**; the deployment operator supplies **endpoints, model IDs and credentials**. End users submit tasks to the application. They do not configure individual nodes.

```text
Node → model alias → deployment binding → local / self-hosted / cloud API
```

Every Python, HTTP and container export includes `model-contract.json`. It lists the OpenAI-compatible `/chat/completions` protocol and each binding's aliases and required capabilities, without provider URLs or credentials. Inspect it before provisioning models:

```bash
python app.py --model-contract
```

A deployment can start with `models: {}` in `deployment.yaml`. The HTTP service starts and exposes its contract at authenticated `GET /model-contract`; task submission returns 503 until its connections are configured. Fill the declared bindings once your models are available:

```yaml
models:
  writing-api:
    base_url: http://127.0.0.1:8000/v1
    model: your-served-model
    api_key_env: null
    capabilities: [text, structured_output]
```

`api_key_env: null` sends no Authorization header, suitable for an unauthenticated local server. For an authenticated API, use an environment variable name such as `MODEL_API_KEY`. For an operator-managed server over HTTP, set `allow_http: true`; HTTPS and loopback HTTP work by default. In a container, `127.0.0.1` refers to that container: use the model service's network hostname when it runs separately.

Start the exported backend with `python serve.py --profile deployment.yaml`. Each new run reads the current model connections. Replacing the endpoint or model ID needs no graph changes or new export; existing runs resume with their recorded connections. Keep the capabilities required by the application when switching models. Provider-specific sampling, JSON and reasoning options remain configurable per connection.

For a centrally hosted application, its operator provisions the models and model keys. For a customer-installed application, its installer or operator supplies the profile and inference services once. Local process startup, GPU selection and preload are optional [service settings](local-models.md), independent of agent behavior. A model with a different wire protocol needs a provider adapter or an OpenAI-compatible gateway.
