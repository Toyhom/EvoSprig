[English](../tools.md) · **简体中文** · [文档目录](README.md)

<a id="tool-connections"></a>

# 工具连接

Python 函数使用 `Tool` 并显式注册。输入/输出 JSON schema、版本、超时、效果类别和幂等性是契约的一部分。同步函数在线程中运行；异步函数在事件循环上运行。`ExternalTool` 为外部执行器托管的任务定义幂等 `submit`、`poll` 和可选的 `cancel` 回调。日志会持久化外部任务 ID。

<a id="scheduled-steps-and-agent-selected-calls"></a>

## 计划步骤与 Agent 选择的调用

对必需步骤（例如 OCR、解析发票或提交视频渲染）使用 `tool` 节点。其输入来自图，运行时直接调用它。当模型应决定是否调用工具时，将同一工具挂到 `agent` 节点。两种情况下工具契约相同。

仅依赖其参数得出结果的本地计算可以声明 `Tool(..., pure=True)`。运行时可以在中断后重复该计算，并用 `execution.pure_checkpoint_interval` 批量处理其检查点。ComfyUI 准备节点将此用于图连接和参数计算；模型调用、文件访问和外部服务使用常规操作日志。参见[大型 ComfyUI 图](comfyui.md#large-graphs)。

<a id="deployment-bindings"></a>

## 部署绑定

HTTP 和 MCP 工具是管理员配置的部署绑定。规格引用逻辑插件名称和版本。配置文件可包含 `models` 和 `tools`：

```yaml
models: {}
tools:
  http.lookup:
    kind: http
    name: http.lookup
    version: '1'
    description: Look up a fact in the project service
    endpoint: https://tools.example/lookup
    method: GET
    auth_env: LOOKUP_TOKEN
    side_effect: read_only
    input_schema:
      type: object
      properties:
        query: {type: string}
      required: [query]
      additionalProperties: false
    output_schema:
      type: object
      properties:
        answer: {type: string}
      required: [answer]
      additionalProperties: false
```

`GET` 将标量输入编码为查询参数；其他受支持的方法发送 JSON。响应必须满足输出 schema。重定向会被拒绝，响应大小和时间有界，错误不包含上游正文。使用 HTTPS 或环回 HTTP 端点。支持去重的写入会设置 `idempotent: true`；服务必须遵守 `Idempotency-Key` 头。授权从引用的环境变量读取，且绝不会序列化到运行或导出中。

使用 `evosprig run agent.yaml --profile deployment.yaml ...`。运行会记录经过验证的工具绑定，因此重启 worker 时会使用原始端点和契约。`evosprig export agent.yaml --profile deployment.yaml --out exported` 打包所需适配器和声明的非机密绑定。它排除内存、数据库和不相关的部署连接。更改服务行为需要新的工具版本和重新进行契约验证。

<a id="mcp-subset"></a>

## MCP 子集

安装 `evosprig[mcp]`。Alpha 固定 Python SDK **1.30.0**、协议 **2025-11-25** 和 **Streamable HTTP**。适配器初始化会话，以有界分页发现工具，在调用前检查固定 schema，并关闭其会话。可通过 `MCPClient` 进行资源读取和提示词检索。收到的指令、资源和提示词作为数据返回；使用它们是应用的显式选择。Sampling、elicitation、roots、OAuth 流程、stdio 和实验性任务扩展不在该适配器的支持矩阵内。

```python
from evosprig.plugins.mcp_tools import MCPClient, MCPConnection

client = MCPClient(MCPConnection(endpoint="http://127.0.0.1:8000/mcp"))
manifest = await client.discover()
print(manifest["protocol_version"], manifest["tools"])
```

将所选工具的 `inputSchema` 和 `outputSchema` 复制到部署条目中，并设置 `kind: mcp`、`name`、`remote_name`、`description`、`endpoint`、`input_schema`、`output_schema` 和显式的 `side_effect`。结构化结果是默认值；对于没有结构化输出契约的工具，`result_format: content` 返回包含内容块的 JSON 对象。仅凭 MCP 注解不会授予写权限。MCP 写入没有通用幂等性保证，因此回执未知的写入会按与非幂等 Python 工具相同的对账规则暂停。

官方 SDK 允许同源上的保留方法重定向。凭据仍为环境引用。适配器拒绝与固定部署契约不同的工具 schema。

来源：[MCP 规范](https://modelcontextprotocol.io/specification/2025-11-25)、[官方 Python SDK](https://github.com/modelcontextprotocol/python-sdk)。

<a id="asynchronous-http-jobs"></a>

## 异步 HTTP 作业

`kind: external_http` 是只写、幂等的作业绑定。配置 `endpoint`、输入/输出 schema 和可选的 `auth_env`，使用与普通 HTTP 工具相同的 HTTPS/环回端点规则。POST 将经过验证的参数作为 JSON 和稳定的 `Idempotency-Key` 头发送，期望 `{"job_id":"safe-id"}`。GET `endpoint/{job_id}` 返回 `{"status":"pending|succeeded|failed|canceled","output":...}`。DELETE 取消。任务 ID 在轮询前记入日志；恢复时查询已保存的 ID。远程服务必须以原子方式将幂等键绑定到其原始参数。参见短片渲染器以获取可执行示例。导入/导出的绑定包含环境引用，恢复的运行会拒绝绑定变更。

<a id="read-only-sqlite"></a>

## 只读 SQLite

在 CLI 运行、Studio 和导出的应用中使用相同的数据库工具：

```yaml
models: {}  # Add your model binding here.
tools:
  database.schema:
    kind: sqlite
    name: database.schema
    operation: schema
    path_env: EVOSPRIG_SQLITE_PATH
    tables: [orders]
  database.query:
    kind: sqlite
    name: database.query
    operation: query
    path_env: EVOSPRIG_SQLITE_PATH
    tables: [orders]
    max_rows: 200
    max_vm_steps: 1000000
```

数据库路径从环境解析。SQLite 以只读方式打开；授权器会阻止写入、附加数据库、扩展以及允许列表之外的表。`schema` 接受 `{}`。`query` 接受 `{"sql":"SELECT ...","parameters":[]}` 并返回 `columns`、`rows` 和 `truncated`。应聚合大型数据集，而不是请求所有行。空的表允许列表允许读取数据库中的所有表。

要从 CSV 准备数据库，请使用 `evosprig data load-csv orders.csv --database
shop.sqlite --table orders`。表头必须是唯一的 SQL 标识符。导入器以事务方式创建新表，并拒绝覆盖现有表。SQLite 的 NUMERIC 亲和性会转换看起来像数字的值，包括前导零标识符；需要显式列类型时，请使用预配置的数据库。数据库文件绝不会包含在导出中。参见[数据分析师](../../examples/data-analyst)。

<a id="let-an-agent-correct-a-tool-call"></a>

## 让 Agent 更正工具调用

AgentSpec 0.3 的 agent 节点可以设置 `tool_errors: feedback`。来自只读工具的无效参数和显式 `ToolFeedbackError` 拒绝会变为工具观察：

```json
{"error":{"code":"sql_error","message":"no such column: sales"}}
```

然后模型可以更正其调用。拒绝会记入日志，正常运行的预算会限制重试。自定义只读工具可以抛出 `ToolFeedbackError(code,
message)`，并附带面向模型的简短消息。不要在该消息中放置凭据和私有传输细节。一般异常、输出 schema 失败和工具允许列表违规仍会停止运行。结果未知的写操作会暂停以进行对账。默认的 `tool_errors: raise` 保留现有的快速失败行为。

<a id="tool-selection-and-concurrent-calls"></a>

## 工具选择与并发调用

AgentSpec 0.3 的 agent 节点可以选择启用可复用工具策略：

```yaml
type: agent
model: main
tools: [search, lookup, calculator]
parallel_tool_calls: true
tool_errors: feedback
tool_selection: relevant
tool_limit: 2
```

`parallel_tool_calls` 会并发执行来自一个模型响应的独立只读调用，并遵守 `execution.max_parallel_tools`。结果按请求顺序返回给模型，每个操作保留其持久回执。写调用和异步任务工具在一个模型响应内仍按顺序执行。图级别的 `parallel` 和 `map` 仍可用于独立分支和批次。

`tool_selection: relevant` 根据节点输入对名称/描述进行排名，并从其现有允许列表中暴露前 `tool_limit` 个工具。它是确定性的词法发现，适用于大型注册表；当应提供所有工具时，选择 `all`。对未暴露工具的模型调用会被拒绝。选择不能发现或授予对未声明工具的访问权限。

`tool_errors: feedback` 让 agent 更正无效参数和显式声明的只读拒绝。只读 HTTP 绑定将状态 400/422 转为通用参数拒绝观察，而不暴露上游响应正文。其他传输/服务器故障仍为终止性错误。不确定的写入仍需要对账。结合 ReAct 风格工具循环、JSON schema 验证、动态 map 和人工审批，这些策略可跨应用使用。

<a id="code-browser-and-ocr-tools"></a>

## 代码、浏览器和 OCR 工具

内置的 `code.python` 解释器运行确定性的 JSON 转换。这些计算使用节点检查点，由 `execution.pure_checkpoint_interval` 控制批处理；模型调用和外部工具操作在开始前会刷新待处理计算。

可选的 [Toolbox](../../apps/toolbox/README.md) 通过标准 HTTP 绑定提供 Python 执行、HTML 交互检查/截图和离线英文 OCR。产物以下载回执形式返回，因此二进制图像不会填满模型上下文。使用相同契约绑定你自己的沙箱或媒体服务。

<a id="bounded-output-repair"></a>

## 有界输出修复

AgentSpec 0.3 中的模型和 agent 节点可以设置 `output_errors: feedback` 和 `max_output_retries: 2`。无效 JSON、schema 不匹配和显式输出限制错误会获得一次有界更正回合。网络错误不会自动重试。所有更正调用都消耗原始运行/研究预算；来自截断响应的已报告用量会在重试前计费；没有用量的调用保留其预留。

agent 还可以设置 `max_tool_rounds: 4`。达到限制后，运行时会移除工具描述符，并根据已收集的观察请求最终答案。这会限制重复检索，而不更改应用的工具或提示词。省略它会保留运行范围的调用限制。

原始论文和实现映射：[研究参考](references.md)。

<a id="shared-team-documents"></a>

## 共享团队文档

使用[工作区工具](shared-workspaces.md)处理带修订的文档、编辑历史和持久唤醒。当写工具在任何副作用之前拒绝请求时，可以抛出 `ToolRejectedError(code, message)`；运行时会记录该拒绝，并给配置了 `tool_errors: feedback` 的 agent 一个更正回合。将此用于失败的前置条件，例如修订冲突。结果不明确的写入失败会进入对账。
