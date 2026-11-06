[English](../deployment.md) · **简体中文** · [文档目录](README.md)

<a id="self-hosting-and-application-deployment"></a>

# 自托管与应用部署

平台提供编辑、评估和版本管理。导出的应用可独立运行选定的版本。

<a id="run-the-platform"></a>

## 运行平台

```bash
python -m pip install -e '.[server,evolution,mcp]'
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --workspace ./state --project examples/hello/agent.yaml \
  --studio-dir apps/studio/dist --max-concurrent-runs 4
```

服务器绑定到 `127.0.0.1:18766`；远程访问请使用 SSH 转发。`--profile deployment.yaml` 提供模型/工具绑定。`--token-env EVOSPRIG_API_TOKEN` 启用工作区令牌。在 Studio 的 Connection 面板中输入相同的令牌。

如需独立的用户身份，请提供 `--auth-file principals.yaml`：

```yaml
- user: alice
  tenant: team
  token_env: EVOSPRIG_ALICE_TOKEN
- user: bob
  tenant: team
  token_env: EVOSPRIG_BOB_TOKEN
```

令牌从服务环境中解析。项目、运行、记忆和候选属于经过身份验证的主体。`--project` 在默认本地身份下导入；经过身份验证的用户应在 Studio 中创建或导入自己的项目。

使用你的进程管理器重启服务。持久化运行会从检查点恢复；不确定的外部写入遵循[对账协议](durable-runtime.md)。默认部署在单台主机上使用 SQLite 和有界异步工作进程。

<a id="persistent-state"></a>

## 持久化状态

工作区包含项目、运行、记忆、共享文档、删除账本、study 和版本数据库。将 SQLite 放在支持随机写入和锁的文件系统上。将大型媒体制品存储在所选的对象存储中。

使用 SQLite 的备份 API 备份数据库，或在取得一致性备份时停止平台。恢复期间保留最新的删除账本，以免已删除的记忆重新出现。通过部署环境重新提供凭据。

<a id="export-an-application"></a>

## 导出应用

```bash
evosprig export examples/hello/agent.yaml --target python --out ./hello-python
evosprig export examples/hello/agent.yaml --target http --out ./hello-http
evosprig export examples/hello/agent.yaml --target container --out ./hello-container
```

对于 HTTP/MCP/外部工具，添加 `--profile deployment.yaml`。导出内容包括行为锁、依赖锁、运行时源代码、文件哈希和外部依赖报告。不支持导出的插件会生成不兼容报告。

在单独的 Python 3.12 环境中安装并运行 HTTP 导出：

```bash
cd hello-http
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --mock --input '{"question":"Hello"}'
# Set EVOSPRIG_SERVICE_TOKEN, then:
python serve.py --mock --workspace ./state
```

应用服务使用回环端口 8080。业务端点需要 `Authorization: Bearer <token>`。`POST /runs` 接受 `{"input": {...}}`；特定运行的路由会暴露状态、事件、人工输入和取消。`/health` 返回可用性和版本。

容器导出包含 Dockerfile、非特权 UID 10001 和持久化的 `/state` 目录。导出的 README 中包含构建和运行说明。对于远程部署，请添加 TLS 反向代理和适当的访问控制。

<a id="import-an-exported-project"></a>

## 导入已导出的项目

```bash
evosprig import hello.zip
evosprig import hello.zip --out ./imported-project
```

Studio 的 Import Project 操作会在创建项目之前检查 ZIP。导入会验证路径、大小、清单、哈希和插件引用，然后加载声明式规格和资源。导入不会执行归档中的 Python。编辑导出的源代码或资源后，请重建版本锁。

<a id="adjustable-execution-defaults"></a>

## 可调整的执行默认值

模型节点继承 `execution.max_output_tokens`（默认 512）；在模型/智能体节点上设置 `max_output_tokens`，以获得更长的交付物。共享令牌和耗时预算仍然适用。`output_errors: feedback` 要求模型修复无效的 JSON/schema 输出或截断内容，默认使用 `max_output_retries: 1`，最多三次。默认策略为 `raise`，因此现有应用会保留其行为。传输错误不是格式错误。

这遵循 [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output) 使用的有界验证反馈模式。根据任务和提供方限制设置输出长度；反复截断可能需要更大的节点限制、更小的任务或能力更强的模型。

独立评估用例可以使用部署配置文件中的 `evaluation.environment.max_concurrent_samples` 并发运行（默认 1，最大 32）。每个用例获得全新的身份和环境。结果保留输入顺序，所有调用共享实验预算，评估失败会取消剩余用例。根据提供方配额和环境容量提高并发数。普通服务单独暴露 `--max-concurrent-runs`（默认 4）。

<a id="model-http-connections"></a>

## 模型 HTTP 连接

OpenAI 兼容适配器在同一提供方会话中跨节点和并发运行复用 HTTP 连接。评估会为一个批次保持任务池和评判池打开；最后一个会话关闭客户端，包括在取消时。模型绑定接受 `max_connections`（默认 32）和 `max_keepalive_connections`（默认 8，不大于总数）。这些限制套接字，而工作流和评估并发设置控制已调度的工作。

对于由 vLLM 提供的 Qwen，在模型绑定中设置 `json_mode: without_tools`。这会使服务器的 JSON 语法不进入工具调用轮次，并在未提供工具时启用。运行时仍会根据节点 schema 验证每个最终答案，并应用其配置的修复预算。默认的 `always` 会在每个 JSON 输出请求上发送 JSON 模式；`off` 将格式化留给模型和运行时验证。

<a id="resident-local-models"></a>

## 常驻本地模型

在部署配置文件中声明模型和工具服务器，预加载一次并在多次运行中复用。Studio 会显示其就绪状态；导出的应用使用相同的服务管理器。参见[预加载本地模型](local-models.md)。

## 应用交付后再绑定模型

导出包包含与厂商无关的 `model-contract.json` 和 `deployment.example.yaml`。部署者可以稍后准备本地推理或 API，再绑定到已交付应用，无需修改智能体。业务客户端只提交任务，模型凭据由应用部署者统一管理。详见[应用与模型解耦](model-connections.md#应用与模型解耦)。
