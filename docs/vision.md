# Images and vision models

[English](vision.md) · [简体中文](zh-CN/vision.md) · [Documentation](README.md)

Model and agent nodes can consume images alongside ordinary structured inputs. Studio also previews image and video assets in run results and human approval steps: select **Show media** to open them. Declare the `vision` capability and select the input bindings that contain images:

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

An image input can contain a URI, an asset with a `uri` field, or a list of either. Supported inputs are HTTPS URLs and PNG/JPEG/WebP base64 data URIs. The runtime does not read local files or fetch URLs implicitly. Provider support varies; Kimi K3.1 Pro requires base64 or its own uploaded-file format. The [local media service](../apps/media-service/) converts generated assets to base64 previews through an explicit read tool.

Studio exposes **Image inputs** in the settings of nodes bound to a vision model. All other inputs remain ordinary text/JSON context. Images are passed as image content parts, rather than JSON strings containing encoded pixels.

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

Kimi uses fixed sampling parameters and always-on reasoning. Its completion-token limit includes reasoning. The provider adapter preserves the complete assistant message for subsequent tool turns; public run events contain usage and outputs, not the provider's private reasoning fields.

`execution.image_token_reserve` defaults to 4096 per image and is configurable. This reserves room before a request; actual provider usage is charged to the run budget afterward. Resize previews or increase the reservation for higher-resolution inputs. A message accepts at most 16 images and 20 MiB of combined URI data.

See [Kimi's model guide](https://platform.kimi.com/docs/guide/kimi-k3-1-pro-quickstart) for its current request contract and [agent resources](agent-resources.md) for per-node output limits.
