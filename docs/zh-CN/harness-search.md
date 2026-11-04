[English](../harness-search.md) · **简体中文** · [文档目录](README.md)

<a id="evolve-the-application-harness"></a>

# 演进应用 harness

选择应用中可能发生变化的部分，提供任务，并运行搜索。候选方案可以包含提示词、技能库、Python 资源、每个智能体的 harness 设置、模型选择和工作流拓扑。EvoSprig 通过其运行时执行完整候选方案，并存储其版本和差异。

<a id="give-each-agent-a-harness"></a>

## 为每个智能体提供 harness

```python
builder.node(
    "analyst", "agent", model="main", instructions={"resource": "analysis"},
    tools=["search"], inputs={"question": {"ref": "input.question"}},
    output_schema={"type": "object"},
    harness={
        "max_tool_rounds": 8,
        "tool_errors": "feedback",
        "output_errors": "feedback",
        "max_output_retries": 1,
        "memory": {"tool": "search", "query_input": "question",
                   "limit": 5, "max_chars": 4000},
    },
)
```

将 `search` 声明为 `memory.search`、`memory.recall` 或 `documents.search`。记忆策略在首次模型调用前检索上下文。harness 字段会覆盖对应节点的默认值；省略的字段保留这些默认值。使用 `spec_version="0.3"`。

在 Studio 中，选择一个智能体，并启用 **Use a per-agent harness**。在其检查器中设置工具轮次、工具选择、输出恢复和记忆检索。

<a id="declare-the-search-space"></a>

## 声明搜索空间

将此保存为 `search-space.yaml`：

```yaml
fields:
  /graph/nodes/analyst/model:
    kind: choice
    choices: [fast, careful]
  /graph/nodes/analyst/harness/max_tool_rounds:
    kind: integer
    minimum: 2
    maximum: 12
  /graph/nodes/analyst/harness/memory/limit:
    kind: integer
    minimum: 1
    maximum: 10
modules:
  instructions: [resource:analysis]
  execution:
    - /graph/nodes/analyst/model
    - /graph/nodes/analyst/harness/max_tool_rounds
  retrieval: [/graph/nodes/analyst/harness/memory/limit]
```

`fast` 和 `careful` 是已在 AgentSpec 中声明的模型别名。每个指针都必须在初始规范中可解析，因此在搜索这些字段之前先配置 harness 字段。数值边界应用于新值；原始值仍可作为基线使用。对于 temperature 等连续参数，使用 `kind: number`。`choice` 也可以包含完整的结构化对象。

```bash
evosprig improve agent.yaml --suite tasks.yaml \
  --method modular_rsi --resource analysis \
  --search-space search-space.yaml --rounds 2 \
  --proposal-output-tokens 4096 --max-evaluations 300 \
  --profile deployment.yaml
```

在 Studio 中，打开 **Improve → Search space and method settings** 并粘贴等效 JSON。通过 `StudyConfig(search_space=...)` 和 study API 也可以使用相同配置。对于特定于方法的控制项，使用 `--method-options options.yaml`。

<a id="search-workflow-topology"></a>

## 搜索工作流拓扑

图维度允许提议者编辑节点、边、有界循环、分支和输入映射：

```yaml
fields:
  /graph: {kind: graph}
tool_grants:
  /new_calculation: [python]
```

每个提议的图都会通过 AgentSpec 验证，包括可达性、引用顺序和嵌套限制。现有节点保留其工具权限。`tool_grants` 会将已声明的工具别名显式分配给新增或变更的节点路径；嵌套路径使用 `/team/body/worker` 或 `/team/branch/worker`。模型绑定、应用 schema、执行预算和部署权限仍由开发者控制。

<a id="evolve-executable-code"></a>

## 演进可执行代码

将转换存储在代码资源中：

```python
builder.resource("totals", "code/totals.py", role="code")
builder.tool("python", "code.python")
builder.node("calculate", "code", tool="python", code="totals",
             inputs={"rows": {"ref": "input.rows"}},
             output_schema={"type": "object"})
```

```python
# code/totals.py
def run(inputs):
    amounts = [row["amount"] for row in inputs["rows"]]
    return {"total": sum(amounts), "count": len(amounts)}
```

内置解释器支持 JSON 值、算术、条件、有界循环、单生成器推导式以及常见的字符串/列表/字典操作。它最多执行 10,000 条指令，程序长度上限为 32,000 个字符，值长度上限为 65,536 个字符。对于 Python 包、文件或网络访问，使用具有相同 `{code, data}` 输入契约的已部署沙箱工具。代码资源会进行语法检查、版本管理，并包含在独立导出中。

选择 `--resource totals`，配合 harness 优化器来搜索实现。当工作流到达代码节点时，代码节点就会运行。智能体也可以在其推理需要时改为调用已声明的工具。

<a id="method-policies"></a>

## 方法策略

这些是所引用方法针对 EvoSprig 候选方案和任务评估的原生适配。

| 方法 | 搜索行为 | `options` 中的主要控制项 |
| --- | --- | --- |
| [SkillOpt](https://arxiv.org/abs/2605.23904) | 锚定、有界的技能补丁；被拒绝编辑的记忆；受保护的慢指导；严格的选择增益 | `edit_budget`, `edit_chars`, `batch_size`, `slow_every` |
| [Evo-Harness](https://arxiv.org/abs/2608.15071) | 有序任务流 → 失败记忆 → 主题/通用技能库；后续任务发现相关过程 | `batch_size`, `general_min_tasks`, `max_skills` |
| [AHE](https://arxiv.org/abs/2604.25850) | 诊断轨迹，声明预测的修复和回归，衡量变更，按目标回退失败的机制 | Study `rounds` |
| [Meta-Harness](https://arxiv.org/abs/2603.28052) | 基于归档的实现、分数和轨迹提出方案；跟踪分数/token 前沿 | Study `rounds` |
| [RRSI](https://arxiv.org/abs/2609.24972) | 重复测量、编辑预算退火、修订历史、机制审查以及分数/成本准入 | `repetitions`, `proposals`, `delta`, `min_edits`, `max_edits`, `beta0`, `beta1` |
| [ADAS](https://arxiv.org/abs/2408.08435) | 设计、评审、实现、评估并保留设计档案 | Study `rounds` |
| [DarwinX](https://arxiv.org/abs/2608.07545) | 分支变异和互补重组；全新父代筛选和重复确认；保留已解决任务 | `repetitions`, `screen_size`, `merge_every`, `regression_tolerance` |
| [ModularRSI](https://arxiv.org/abs/2609.14857) | 独立模块分支、同任务对比、差异审查、不相交集成和联合执行检查 | `repetitions`, `integration_rounds`; `search_space.modules` |
| [Arbor](https://github.com/RUC-NLPIR/Arbor) | 协调器扩展/选择/剪枝假设；实验从当前主干开始；洞察传播到祖先 | `max_depth`, `coordinator_actions` |

SkillOpt 和 Evo-Harness 需要挂载 `skill` 资源。Evo-Harness 在这些资源中存储可发现的过程，这些过程带有触发器和源任务 ID。RRSI 需要已报告的正任务 token 成本；其默认不确定性区间来自重复的基线分数，或设置显式的 `delta`。其新颖性项衡量新近改进的可编辑目标。ModularRSI 将每个目标分配给一个模块，并在分支内使用执行/审查门禁。DarwinX 使用重复的搜索任务测量来准入分支并选择其结果。仅当搜索分数和选择分数都提高时，Arbor 才推进主干。

AHE 返回其保留的修订；Evo-Harness 返回累积的库；ModularRSI 返回经检查的集成。ADAS 和 Meta-Harness 按验证分数选择。随后，每种方法的结果都会经过相同的独立发布评估和采用控制。

<a id="evaluate-actions-and-state"></a>

## 评估动作与状态

对于写作任务，从任务输入和 LLM 评判器开始。对于代码或业务操作，添加执行检查和可观察的环境状态。`evaluation.environment.workspace_writes: true` 在评估期间启用有作用域的共享文档和对等消息。每个样本都会获得全新的身份和工作区状态。[行业环境适配器](industry-environments.md) 提供业务操作和最终状态检查。

参见 [评估](evaluation.md)、[方法要求](method-requirements.md) 和 [优化器插件](optimizer-plugins.md)。
