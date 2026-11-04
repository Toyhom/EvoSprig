# Models for each agent

Every model or agent node selects its own **model binding**. Give a writer a text model, a visual reviewer a multimodal model, and a tool-using role a model with tool calls. Different bindings can use different vendors or local servers in the same application.

In Studio, open **Model connections** in the sidebar. Choose a provider address, enter its model ID and the name of its API-key environment variable, then save. Select an agent and choose that connection under **Model**. Enable image support only for a model that accepts images; select the node's image inputs separately.

| Connection | Base URL |
| --- | --- |
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com` |
| Kimi | `https://api.moonshot.cn/v1` |
| MiniMax | `https://api.minimax.io/v1` |
| Qwen / DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Local vLLM or another OpenAI-compatible server | e.g. `http://127.0.0.1:8000/v1` |

Use the model ID and regional endpoint provided by your account. Set credentials in the server's environment. Provider-specific reasoning and token options are documented in [vision and provider options](vision.md).

The SDK uses the same binding:

```python
builder.model("writer", "writing-api", ["text", "structured_output"])
builder.model("reviewer", "local-vision", ["text", "structured_output", "vision"])
# Set model="writer" or model="reviewer" on each node.
```

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
    api_key_env: LOCAL_MODEL_API_KEY
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
