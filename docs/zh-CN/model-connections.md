[English](../model-connections.md) · **简体中文** · [文档目录](README.md)

<a id="default-model-and-node-overrides"></a>

# 默认模型与节点覆盖

为应用设置一个默认连接，然后在各个节点需要不同模型时覆盖这些节点。每个模型或 Agent 节点都会选择一个**模型绑定**。为撰写者指定文本模型，为视觉审阅者指定多模态模型，为使用工具的角色指定支持工具调用的模型。同一应用中的不同绑定可以使用不同供应商或本地服务器。

在 Studio 中，打开侧边栏中的**模型连接**。选择一个提供商地址，输入其模型 ID 以及其 API 密钥环境变量的名称，然后保存。选择**应用默认模型**来设置 `main`。选择一个 Agent，并在**模型**下选择另一个连接，以进行节点特定覆盖。新建的模型节点使用 `main`；现有的显式别名保持其选择。仅为接受图像的模型启用图像支持；单独选择该节点的图像输入。

| 连接 | 基础 URL |
| --- | --- |
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com` |
| Kimi | `https://api.moonshot.cn/v1` |
| MiniMax | `https://api.minimax.io/v1` |
| Qwen / DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 本地 vLLM 或其他 OpenAI 兼容服务器 | 例如 `http://127.0.0.1:8000/v1` |

使用你的账户提供的模型 ID 和区域端点。在服务器的环境中设置凭据。提供商特定的推理与 token 选项记录在[视觉与提供商选项](vision.md)中。

<a id="python-one-default-optional-overrides"></a>

## Python：一个默认值，可选覆盖

为通用模型使用单个变量。`default_model()` 定义 `main` 别名。省略 `model` 的节点会继承它，包括 map、loop 和 parallel 子流中的节点。显式别名优先。

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

保存的 AgentSpec 包含显式的 `model: main` 引用，因此导出内容和运行时使用相同的选择。对于手写 YAML，在共享默认值的节点上设置 `model: main`。重新绑定 `models.main.binding`，以一起更改它们的连接。

对于多个显式角色：

```python
builder.model("writer", "writing-api", ["text", "structured_output"])
builder.model("reviewer", "local-vision", ["text", "structured_output", "vision"])
# Set model="writer" or model="reviewer" on each node.
```

<a id="deployment-connections"></a>

## 部署连接

在 `deployment.yaml` 中配置这些部署连接：

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

`local_service` 将模型连接与其常驻服务关联。使用该连接的节点上会显示**Preload**；运行和导出的应用还会根据其部署配置准备自启动服务。使用此连接的多个节点共享已加载的服务器。参见[预加载与保留](local-models.md)。

使用 `--profile deployment.yaml` 启动 Studio 以编辑这些连接。节点到绑定的选择随应用进行版本管理；端点和凭据属于部署。在配置了多个用户身份的服务器中，其操作员维护共享连接文件。
