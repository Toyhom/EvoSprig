[English](../quickstart.md) · **简体中文** · [文档目录](README.md)

<a id="quickstart"></a>

# 快速开始

需要 Python 3.12+。构建 Studio 还需要 Node.js 20+。

<a id="install-and-run"></a>

## 安装并运行

```bash
git clone https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python -m pip install -e '.[server,evolution,mcp]'
evosprig validate examples/hello/agent.yaml
evosprig run examples/hello/agent.yaml --mock --input '{"question":"Hello EvoSprig"}'
```

示例会调用文本统计工具，然后将问题和结果传给模型。`--mock` 使用确定性的离线响应。使用 `python examples/hello/build_agent.py` 从 Python 重新构建其规格。

| 附加项 | 增加的内容 |
| --- | --- |
| `models` | 兼容的模型 API |
| `server` | 本地 HTTP API 和 worker |
| `evolution` | 官方 GEPA 库 |
| `mcp` | MCP 工具客户端 |
| `media` | 动态图形渲染器依赖 |
| `dev` | 开发和测试工具 |

<a id="connect-a-model"></a>

## 连接模型

在 shell 或密钥管理器中设置 `DEEPSEEK_API_KEY`，然后运行：

```bash
evosprig run examples/hello/agent.yaml \
  --profile examples/deployment.example.yaml \
  --input '{"question":"What is 2 + 3?"}'
```

示例配置使用 `https://api.deepseek.com` 和 `deepseek-flash`。对于其他兼容提供商，请在你自己的配置中更改 `base_url`、`model`、`api_key_env` 和 capabilities。将凭据保存在环境变量中。本地推理服务可使用回环 HTTP。

<a id="open-studio"></a>

## 打开 Studio

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --workspace .evosprig/studio \
  --project examples/hello/agent.yaml --studio-dir apps/studio/dist
```

打开 **http://127.0.0.1:18766**。Studio 以英文启动，并在侧边栏提供可持久化的中文语言选项。

1. 选择一个项目或创建一个项目。添加节点、连接其端口并编辑其参数。
2. 保存工作流并运行。实时模式使用服务器的模型配置和环境。
3. 在 **Resources** 中编辑提示词，在 **History** 中检查执行情况，在 **Memory** 中管理事实。
4. 在 **Improve** 中导入任务套件，选择可编辑资源、方法和预算。
5. 在 **Versions** 中比较候选版本，然后启用、回滚或导出版本。

保存失败时，未保存的更改会保留。Studio 会在替换草稿前提示。如果另一位编辑者更改了修订版本，保存会返回冲突；重试前请将本地草稿与最新版本进行比较。

进行远程开发时，请通过 SSH 转发回环端口。使用 `--port` 选择其他端口，并使用 `--token-env EVOSPRIG_API_TOKEN` 要求 API 令牌。[部署指南](deployment.md)。

<a id="run-an-application"></a>

## 运行应用

[示例库](../../examples/README.md) 包含视频制作、多智能体研究、基于审批的支持和持久记忆。每个示例都有一个可运行的入口点，并说明其模型/工具依赖项。

<a id="export-an-independent-application"></a>

## 导出独立应用

```bash
evosprig export examples/hello/agent.yaml --out .evosprig/exports/hello
cd .evosprig/exports/hello
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --mock --input '{"question":"Hello"}'
```

为导出的应用使用单独的 Python 环境。导出内容包含 AgentSpec、资源、可读的 Builder 代码、运行时源代码和依赖锁定文件。在部署主机上提供服务凭据。HTTP 和容器目标会添加独立服务器；请参阅[部署](deployment.md)。

<a id="development"></a>

## 开发

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
ruff check src tests examples scripts
pytest -q
npm --prefix apps/studio test
```

浏览器测试使用端口 18765 上的临时 API。使用特定解释器或工作区时，设置 `EVOSPRIG_PYTHON` 和 `EVOSPRIG_TEST_WORKSPACE`。进行前端热重载时，运行 `npm --prefix apps/studio run dev`；`EVOSPRIG_API_PORT` 设置后端代理端口。
