[English](../durable-runtime.md) · **简体中文** · [文档目录](README.md)

<a id="durable-runtime"></a>

# 持久化运行时

AgentSpec 0.2 新增 `transform`、`condition`、`join`、有界的 `loop`、具名的 `parallel` 分支以及 `human` 输入节点。原始 0.1 文档保留其规范表示。条件使用类型化谓词；不会求值任何 Python 表达式。条件边携带 `when: true|false`，而 `join: selected` 节点合并已运行的分支。循环输出成为下一次迭代的输入。`max_iterations` 与共享执行预算约束嵌套图。

CLI 和本地 API 将冻结版本、节点输出、模型消息、操作回执和事件持久化到 SQLite 中。Worker 领取会过期的租约，并使用单调递增的 generation 拒绝陈旧提交。已完成的工作在重启后复用。多个本地 Worker 可共享日志。SQLite 文件和锁需要支持锁定机制的文件系统；对象存储不适用。

租约续期独立于执行循环运行。SQLite 将租约、取消和调度状态与检查点分开存储，因此轮询多模态运行不会反序列化其图像和消息历史。现有日志在打开时以原子方式迁移；升级前请停止较旧的 Worker。大型检查点字符串（16 KiB 及以上），包括内联图像预览，会在同一 SQLite 事务中按每次运行仅存储一次。检查点通过内容哈希引用这些值；读取时会恢复原始 JSON。状态变更会重写紧凑引用，而未改变的媒体保持原处。备份完整的 SQLite 数据库，其中同时包含状态及其 blob。

`Runtime(..., lease_seconds=30)` 设置适合你的存储延迟的租约时长。快照和操作写入会继续检查 Worker 的 generation 和到期时间。

`execution.timeout_seconds` 限制跨恢复的活跃 Worker 时间。默认值为 60 秒；AgentSpec 0.3 允许长时应用最多 86,400 秒。为人工输入或外部作业而挂起的时间不计入。请为外部工具的 `job_timeout_seconds` 单独配置其渲染或执行截止时间。

停机恢复后，运行时先查询已有外部作业的状态，再判断等待期限。已完成的结果会直接取回；超过期限仍在等待或无法连接的作业返回 `external_timeout`。

修复服务或部署问题后，可以显式重试失败的运行：

```python
runtime.retry_failed(run_id)
result = await runtime.resume(run_id)
```

重试保留冻结版本、已完成节点、外部作业 ID、操作回执和已用预算。`run.retry_requested` 事件记录之前的错误。外部作业本身失败或取消时，先在对应服务中恢复作业；需要修改工作流或预算时，启动新运行或调试选定子流程。

```bash
evosprig run agent.yaml --input '{"text":"draft"}' --mock --workspace ./workspace
evosprig runs --workspace ./workspace
evosprig resume RUN_ID --workspace ./workspace --path graph/approval --response '{"text":"approved"}'
evosprig cancel RUN_ID --workspace ./workspace
```

`human` 节点根据其输出 schema 校验响应，并在 `waiting_input` 中暂停。恢复时保留原始版本，即使可编辑项目已更改。API 在 `/api/projects/{id}/runs` 和 `/api/runs/{id}` 下提供运行历史、输入、恢复、取消以及可恢复的 SSE。

使用 `GET /api/runs/{id}/nodes/{node_path}` 检查已保存的步骤，例如 `graph/shots/item-1/takes/iteration-0/render`。响应包含该步骤的输入、输出、状态、纠正反馈和画布位置。节点失败会发出 `node.failed`；运行错误包含第一个失败的 `node_id`。Studio 使用这些记录打开对应条目或 take 进行调试。

写入工具需要持久化日志、运行时 `allow_writes=True` 和规范 `execution.allow_side_effects: true`。幂等工具必须遵守所提供的操作键。回执未知的非幂等操作会暂停以进行对账；若没有 `recover` 钩子，则无法安全重放。外部作业必须支持幂等提交；日志保留其作业 ID 以进行轮询和取消。运行时从不断言跨任意外部服务的事务性。

并行调用共享模型/工具信号量和预算预留。未返回用量的调用保留其预留的 token 额度。Token 用量和未报告调用可观测；在没有计费数据时，货币成本仍然未知。优雅关闭会为工作创建检查点，而硬中断会等待租约到期。同步 Python 工具线程可能在超时后完成：对于需要恢复的副作用，请使用幂等性或外部作业适配器。

<a id="work-over-a-dynamic-list"></a>

## 处理动态列表

AgentSpec 0.3 新增 `map`，用于在运行时生成的任务列表。为它提供 `items` 绑定和主体图。每个主体接收 `input.item`、`input.index` 和 `input.context`（map 节点解析后的 `inputs`）。结果在 `nodes.<map>.output.items` 中保留输入顺序。

```python
builder.map(
    "research",
    items={"ref": "nodes.plan.output.tasks"},
    inputs={"question": {"ref": "input.question"}},
    body=research_graph,
    max_items=6,
    output_schema={"type": "object"},
)
```

`Builder.map` 选择规范版本 0.3。Studio 提供同一节点，包括在 JSON 检查器中显示其主体。`max_items` 默认值为 32（最大 256）；空列表返回空结果列表。非列表输入和超大列表会在主体执行前失败。诸如 `graph/research/item-0/research` 的逐项路径使检查点、审批和外部作业彼此区分。运行恢复时，已完成项会被复用。

每个 map 通过 `max_parallel_nodes` 限制在途主体图的数量。所有嵌套工作还共享运行的模型/工具信号量、token 额度和步骤预算。需要并行工具时，请设置 `max_parallel_tools`。使用 [research team](../../examples/research-team) 和 [video studio](../../examples/video-studio) 作为模板。
