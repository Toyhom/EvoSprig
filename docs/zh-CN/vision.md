[English](../vision.md) · **简体中文** · [文档目录](README.md)

<a id="images-and-vision-models"></a>

# 图像与视觉模型

模型和智能体节点可以将图像与普通结构化输入一同使用。Studio 还会在运行结果和人工审批步骤中预览图像与视频资产：选择 **显示媒体** 即可打开。声明 `vision` 能力，并选择包含图像的输入绑定：

```python
builder.model("reviewer", "vision-model", ["text", "vision", "structured_output"])
builder.node(
    "review", "model", model="reviewer",
    instructions="Review the frame against the requested scene. Return JSON.",
    inputs={
        "scene": {"ref": "input.scene"},
        "frames": {"ref": "input.frames"},
    },
    image_inputs=["frames"],
    response_format="json", output_schema={"type": "object"},
)
```

图像输入可包含一个 URI、带有 `uri` 字段的资产，或由上述任一类型组成的列表。支持的输入为 HTTPS URL 以及 PNG/JPEG/WebP base64 数据 URI。运行时不会隐式读取本地文件或抓取 URL。各提供商的支持情况不同；Kimi K3.1 Pro 要求使用 base64 或其自有的已上传文件格式。[本地媒体服务](../../apps/media-service) 通过显式的读取工具将生成的资产转换为 base64 预览。

Studio 会在绑定到视觉模型的节点设置中显示 **图像输入**。所有其他输入仍为普通文本/JSON 上下文。图像以图像内容部分的形式传递，而不是包含编码像素的 JSON 字符串。

<a id="kimi-k31-pro"></a>

## Kimi K3.1 Pro

```yaml
models:
  vision-model:
    base_url: https://api.moonshot.cn/v1
    model: kimi-k3.1-pro
    api_key_env: MOONSHOT_API_KEY
    capabilities: [text, vision, tool_calling, structured_output]
    token_limit_field: max_completion_tokens
    send_sampling_parameters: false
    timeout_seconds: 300
    options:
      reasoning_effort: low
```

Kimi 使用固定采样参数和始终启用的推理。其补全 token 上限包含推理内容。提供商适配器会为后续工具轮次保留完整的 assistant 消息；公开的运行事件包含用量和输出，不包含提供商的私有推理字段。

`execution.image_token_reserve` 默认值为每张图像 4096，且可配置。这会在请求前预留空间；实际提供商用量随后计入运行预算。对于更高分辨率的输入，请调整预览大小或增加预留量。单条消息最多接受 16 张图像，以及合计 20 MiB 的 URI 数据。

当前请求契约参见 [Kimi 的模型指南](https://platform.kimi.com/docs/guide/kimi-k3-1-pro-quickstart)，每个节点的输出限制参见 [智能体资源](agent-resources.md)。
