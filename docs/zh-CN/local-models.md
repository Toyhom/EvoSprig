[English](../local-models.md) · **简体中文** · [文档目录](README.md)

<a id="preload-local-models"></a>

# 预加载本地模型

在多次运行、节点调试和导出的应用程序之间保持模型服务器存活。部署环境拥有该服务；结束一次 agent 运行后，该服务仍保持已加载状态。

在部署配置中添加一个 `services` 部分：

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

示例使用无需认证的回环服务。需要认证时设置 `api_key_env: LOCAL_MODEL_API_KEY`，并在环境中提供该变量。在 `command` 中使用相应环境的可执行文件；参数会直接传递，不经过 shell。相对的 `cwd` 值相对于配置目录解析。请在机器所分配的 GPU 范围内启动 GPU 服务。

```bash
evosprig services start --profile deployment.yaml
evosprig services status --profile deployment.yaml
evosprig run agent.yaml --profile deployment.yaml --input-file task.json
evosprig services stop --profile deployment.yaml --name director
```

`run` 和 `serve` 会自动准备已配置的服务。对于手动预加载的服务，请设置 `autostart: false`。在 Studio 中，打开 **本地模型与工具** 检查就绪状态，或预加载已配置的服务。

使用 Python SDK 时，在构造运行时之前，从 `evosprig.local_services` 调用 `prepare_services("deployment.yaml")`。重复调用会复用已就绪的服务。对于需要身份验证的健康检查或预热端点，将服务的 `auth_env` 设置为其 bearer token 环境变量的名称。

就绪状态分为两个阶段：HTTP 端点必须响应，然后 `ready` 中的每个字段都必须与健康检查响应匹配。预热端点可能会将加载排队；EvoSprig 会等待就绪字段。请使用报告已加载权重的健康检查字段，而不是仅报告监听端口。媒体服务的 `loaded` 字段标识常驻模型系列。其默认值 `idle_unload_seconds: 0` 会保留该系列。对于并发的图像、视频和语音模型系列，请在合适的设备上部署独立的服务进程；当要求加载另一个系列时，单个媒体工作进程会切换系列。

服务共享位于配置目录旁的注册表，路径为 `.evosprig-services`。使用同一配置文件的并发启动会复用一个进程和一次预热。新的运行和服务器重启会重新连接。日志会保留在注册表中，用于启动诊断。显式调用 `stop` 时，仅会在检查进程身份后终止由该注册表启动的进程。现有端点会被复用，并仍由操作员控制。当多个应用程序应共享一个模型时，请使用一个共享的配置目录。

Python、HTTP 和容器导出中也包含相同的支持。在 Python 导出中，运行 `python -m evosprig.local_services services start --profile deployment.yaml`；`app.py --profile deployment.yaml` 也会准备服务。将应用程序迁移到另一台机器时，请将部署命令和模型路径保留在您自己的配置中。

有关 Episode Studio 完整的模型下载和启动流程，请使用其[应用程序启动器](../../apps/episode-studio/README.md)。ComfyUI 服务器变得可访问并不会加载每个 checkpoint：请为所选 recipe 使用模型加载预热图，或在首次渲染后保留缓存。

<a id="different-models-on-different-gpus"></a>

## 在不同 GPU 上使用不同模型

节点选择模型别名；别名指向部署连接；`local_service` 指向要预加载的进程。每个进程都有自己的 `gpu_devices` 列表。多个节点可以共享同一连接和常驻权重。

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

使用 `CUDA_VISIBLE_DEVICES=3,7` 时，`[0]` 选择物理 GPU 3，`[1]` 选择物理 GPU 7。这些值是**当前分配内的位置**。没有 `CUDA_VISIBLE_DEVICES` 时，它们就是物理索引。省略 `gpu_devices` 可继承该分配；超出范围的位置会被拒绝。

要让一个模型跨两个 GPU 运行，请设置 `gpu_devices: [0, 1]`，并配置服务引擎的张量并行，例如在 vLLM 中使用 `--tensor-parallel-size 2`。仅设备可见性不会分片权重。请安装支持您模型的服务引擎版本，并为权重、缓存和并发请求预配足够的 VRAM。

在 Studio 中，使用 **本地模型与工具 → GPU 位置 → 保存卡分配 → 预加载**。更改受管服务的放置位置前，请先停止该服务；然后再次预加载。已在此管理器之外运行的服务器会保留其现有放置位置。服务状态会显示受管进程解析后的 `CUDA_VISIBLE_DEVICES`。

<a id="service-configuration-reference"></a>

## 服务配置参考

| 字段 | 默认值 | 用途 |
| --- | --- | --- |
| `health_url` | 必填 | 返回 JSON 对象的回环 HTTP 端点 |
| `command` | `[]` | 可执行文件和参数；为空表示连接到现有服务器 |
| `cwd` | `.` | 工作目录，相对于配置目录 |
| `gpu_devices` | 省略 | 要暴露给子进程的 GPU 位置 |
| `warmup_url`、`warmup_body` | 省略、`{}` | 启动模型加载的可选 HTTP POST |
| `ready` | `{}` | 必须匹配的顶层健康检查字段；使用预热时必填 |
| `auth_env` | 省略 | 用于健康检查/预热请求的 bearer token 环境变量 |
| `timeout_seconds` | `1800` | 启动和就绪截止时间，最大 7200 |
| `poll_seconds` | `2` | 就绪轮询间隔，最大 60 |
| `autostart` | `true` | 启动 run/serve 时准备此服务 |
| `retention` | `persistent` | 保留到显式停止或主机分配结束 |

管理器会为本地子进程选择设备。集群调度和远程服务器仍由您的部署环境管理。使用[模型连接](model-connections.md)将远程端点绑定到节点。
