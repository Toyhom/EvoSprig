# Python SDK 与 AgentSpec 参考

[English](../sdk.md) · **简体中文** · [文档目录](README.md)

## Builder

从 `evosprig.sdk` 导入 `Builder`。配置方法返回 builder，可链式调用；`build_spec()` 返回已校验的 `AgentSpec`。

| 方法 | 参数与行为 |
| --- | --- |
| `Builder(project_id, input_schema, output_schema, *, spec_version="0.1")` | 创建图；map 和当前应用能力使用 `"0.3"` |
| `default_model(binding, requires=None)` | 声明 `main`；未指定模型的节点递归继承它，默认能力为 `text` |
| `model(name, binding, requires=None)` | 声明节点使用的模型别名，关联部署连接 |
| `tool(name, plugin, version="1")` | 声明工具别名及插件契约 |
| `resource(name, path, role="prompt")` | 声明提示词、技能或代码文件；路径相对规格文件，名称不得重复 |
| `skill(name, path)` | `role="skill"` 资源的简写 |
| `node(node_id, node_type, *, entry=False, **config)` | 添加节点；默认第一个节点为入口，也可显式指定 |
| `edge(source, target, *, when=None)` | 添加依赖；`when=True/False` 选择条件分支 |
| `map(node_id, *, items, body, output_schema, inputs=None, max_items=32, carry=None)` | 添加 map；`carry` 将上一项的输出传给下一项 |
| `output(**bindings)` | 设置图输出的引用或常量 |
| `execution(**limits)` | 设置运行预算和执行策略 |
| `build_spec()` | 复制、解析默认模型并校验，不改写 builder 原始数据 |

可运行代码：[第一个智能体](../tutorials/first_agent.py)、[漫画应用](../../examples/comic-studio/build_agent.py)。

## AgentSpec 与数据绑定

完整的 [AgentSpec JSON Schema](../assets/agent-spec.schema.json)列出所有字段、枚举、默认值和范围；Python 定义位于 [core/spec.py](../../src/evosprig/core/spec.py)。

| 顶层字段 | 含义 |
| --- | --- |
| `spec_version`, `id` | 契约版本、应用标识 |
| `input_schema`, `output_schema` | 应用输入和输出的 JSON Schema |
| `models` | 模型别名 → 部署连接及所需能力 |
| `tools` | 工具别名 → 插件 ID 和版本 |
| `resources` | 资源名 → 相对路径和用途 |
| `graph` | 入口、节点、边和输出绑定 |
| `execution` | 步数、模型、token、时间及副作用策略 |

输入用 `{"ref": "input.story"}` 或 `{"ref": "nodes.writer.output.text"}` 引用数据，用 `{"value": ...}` 表示常量。可选引用设置 `optional: true` 和 `default`。子流程的 `input` 是自己的输入对象；map 的 body 接收 `item`、`index` 和 `context`，loop 把 body 输出交给下一轮。参见[执行结构](architecture.md)和[漫画 map 示例](../../examples/comic-studio/agent.yaml)。

## 节点类型

所有节点都有 `type`、`inputs` 和 `output_schema`。Schema 检查字段组合，拒绝未知配置。

| 类型 | 职责和主要字段 |
| --- | --- |
| `model` | 单次模型任务：`model`、`instructions`、`skills`、`response_format`、`image_inputs` |
| `agent` | 带工具循环的模型角色：模型字段加 `tools`、`harness`，可选 `mailbox` |
| `tool` | 流程必经的确定性调用：`tool` 与类型化输入 |
| `code` | 受限 JSON 变换：`tool`、`code` 资源、`code_max_value_chars` |
| `transform` | 将解析后的输入作为对象返回 |
| `condition` | 计算 `condition`，按 `when` 选择出边 |
| `join` | 汇合分支；`join` 为 `all` 或 `selected` |
| `loop` | 执行 `body`，最多 `max_iterations` 轮，`until` 可提前停止 |
| `parallel` | 执行命名 `branches` 并汇总输出 |
| `map` | 对 `items` 执行 `body`；`max_items` 限制输入数量，可设 `carry` |
| `human` | 暂停，等待符合 `output_schema` 的响应 |

结构化 `harness` 用于 agent 节点。非空 harness 配置覆盖节点同名字段，省略项保留节点设置。节点输出上限覆盖应用的单次输出上限，同时受共享运行预算约束。[提示词、技能与 harness 字段](agent-resources.md)。

## 编译、保存与运行

`save_spec(spec, path)` 写 YAML；`load_spec(path)` 读取并校验。`compile_agent(spec, root=".")` 冻结已加载的规格及相对于 `root` 的资源文件；从文件编译可用 `compile_agent(load_spec(path), path.parent)`；`compile_snapshot(spec, resources)` 冻结内存中的资源文本。这些函数分别位于 `evosprig.core.spec` 和 `evosprig.core.version`。

从 `evosprig.core.runtime` 导入 `Runtime`，传入模型映射和可选 `ToolRegistry`；关键字参数为 `journal`、`allow_writes=False` 和 `lease_seconds=30.0`。通过 `evosprig.config` 构造部署模型/工具绑定；本地模型运行前调用 `prepare_services(profile)`。

| Runtime 操作 | 结果 |
| --- | --- |
| `await runtime.run(version, inputs, *, run_id=None, scope=None, cancel=None, on_event=None, shutdown=None)` | 执行并返回 `RunResult` |
| `runtime.create_run(version, inputs, *, run_id=None, scope=None, context=None)` | 持久化运行，交给 worker 执行 |
| `await runtime.resume(run_id, *, scope=None, cancel=None, on_event=None, shutdown=None)` | 从冻结版本和检查点继续 |
| `runtime.retry_failed(run_id, *, scope=None)` | 显式重试失败运行，保留已完成工作、预算用量和失败事件 |
| `runtime.get(run_id, scope=None)` | 读取当前状态 |
| `await runtime.cancel_run(run_id, *, scope=None)` | 请求取消并返回当前状态 |
| `runtime.create_event_run(version, inputs, trigger, *, scope=None)` | 创建幂等的事件触发运行 |

`RunResult` 包含 `run_id`、`agent_version`、`status`、`output`、`error`、`events`、`usage`、`duration_seconds` 和 `waiting`，可用 `to_dict()` 序列化。等待工具或人工输入时会保留已完成步骤；续接与对账见[持久运行](durable-runtime.md)。

## 命令行

`evosprig --help` 列出命令组，`evosprig COMMAND --help` 列出参数。主要命令：

```bash
evosprig validate agent.yaml
evosprig run agent.yaml --profile deployment.yaml --workspace .evosprig --input-file task.json
evosprig runs --workspace .evosprig
evosprig inspect RUN_ID --workspace .evosprig
evosprig resume RUN_ID --workspace .evosprig
evosprig cancel RUN_ID --workspace .evosprig
evosprig serve --project agent.yaml --profile deployment.yaml --studio-dir apps/studio/dist --port 18766
evosprig export agent.yaml --target python --out application
evosprig import application.zip --out imported
```

`--mock` 使用测试模型，`--allow-writes` 允许已配置的写工具。`serve` 默认同时执行 4 个运行，可按服务容量修改 `--max-concurrent-runs`。其他命令组：[本地服务](local-models.md)、[数据与评估](evaluation.md)、[自进化](evolution.md)、[ComfyUI](comfyui.md)、[行业环境](industry-environments.md)。
