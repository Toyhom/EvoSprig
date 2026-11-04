[English](../extend-framework.md) · **简体中文** · [文档目录](README.md)

<a id="extend-evosprig"></a>

# 扩展 EvoSprig

核心契约位于 `src/evosprig/core`。具体的模型、工具和记忆实现位于 `plugins`；优化算法位于 `evolution`。CLI、Studio 和导出的应用使用同一运行时。

<a id="extension-contracts"></a>

## 扩展契约

| 添加一个… | 实现 | 注册或绑定 | 起点 |
| --- | --- | --- | --- |
| 自我进化算法 | 接收 `EvolutionContext` 的异步优化器 | `register_method` / `evosprig.evolution` 入口点 | [优化器插件](optimizer-plugins.md) |
| 模型提供方 | `ModelProvider.complete(ModelRequest) → ModelResponse` | 在 `Runtime(models=...)` 中传入；为 CLI 添加部署恢复 | [OpenAI 兼容提供方](../../src/evosprig/plugins/openai_compatible.py) |
| 本地工具 | 带输入/输出 JSON schema 的 `Tool` | `ToolRegistry.register` 和 `Builder.tool` | [工具契约](tools.md) |
| 长时间运行的服务 | `ExternalTool.submit`、`poll`，可选 `cancel` | 注册表或 `external_http` profile 绑定 | [媒体服务](../../apps/media-service) |
| 记忆后端 | `MemoryStore` | 在模型参数之外绑定作用域；注册记忆工具 | [记忆接口](../../src/evosprig/core/memory.py) |
| 任务评分器 | 返回所声明指标结果的可调用评分器 | `Evaluator(..., scorers=...)` | [评估](evaluation.md) |
| 评估环境 | `prepare`、`observe`、`cleanup` | `Evaluator(..., environment=...)` | [环境协议](../../src/evosprig/evaluation/environment.py) |
| 应用 | AgentSpec、资源和工具绑定 | CLI / Studio / SDK | [应用开发者指南](build-applications.md) |

<a id="runtime-changes"></a>

## 运行时变更

新的节点行为会影响规范、引擎、画布映射和编辑器。请保持这些接口一致：

- `core/spec.py`：类型化配置、引用和图校验。
- `core/engine.py`：执行、检查点、取消和共享预算。
- `server/canvas.py` 和 `apps/studio`：呈现与编辑。
- `exporters/python.py`：独立应用所需的模块和绑定。

测试操作中断后的恢复，包括重试该操作是否可能重复写入。`ToolRejectedError` 用于在任何副作用发生之前被拒绝的写入；有歧义的失败使用现有的协调路径。参见[持久化运行时](durable-runtime.md)。

<a id="shared-state-and-applications"></a>

## 共享状态与应用

[WorkspaceStore](shared-workspaces.md) 为工具和浏览器客户端提供共享的、带修订版本的文档存储。记忆提供作用域内的事实和检索；项目资源提供带版本的智能体指令。请根据数据的生命周期选择合适的存储。

[CoworkOS 复现](../../examples/cowork) 展示了主智能体、由运行时协调的专家、共享文档编辑和持久化唤醒。其 Web 界面调用标准 project/run/document API。

<a id="development-and-review"></a>

## 开发与评审

安装和检查请遵循[贡献指南](../../CONTRIBUTING.md)。为新的公开能力提供可运行示例，更新其指南，并运行覆盖变更行为的测试。保持英文和中文面向用户的界面一致。
