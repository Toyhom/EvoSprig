[English](../evolution.md) · **简体中文** · [文档目录](README.md)

<a id="self-evolving-agents-and-controlled-rsi"></a>

# 自进化 agent 与受控 RSI

用自己的任务进化智能体的提示词、技能、代码和运行配置。选择一个节点或应用资源，配置评估方法与搜索上限，再比较各个版本。

自改进循环会修订应用资源，重新运行相同任务，并利用反馈生成更多候选。你控制哪些资源可以更改、预算和版本采纳。

EvoSprig 提供 **涵盖 21 个方法族的 23 种免训练策略**。它们共享相同的应用运行时、评估器、候选存档和发布门禁。GEPA 使用其官方库；其他策略是针对资源和应用运行框架的原生适配，具备下述机制。

<a id="choose-a-strategy"></a>

## 选择策略

| 策略 | 变更内容 | 所需反馈和数据 | 实现 |
| --- | --- | --- | --- |
| [OPRO](https://arxiv.org/abs/2309.03409) `opro` | 指令 | 任务输入和标量分数 | 分数历史提议 |
| [GEPA](https://arxiv.org/abs/2507.19457) `gepa` | 选定的提示词组件 | 分数、执行轨迹和文本反馈 | 官方 `gepa==0.1.4` 适配器；Pareto 选择和轮转组件 |
| [EvoPrompt GA](https://arxiv.org/abs/2309.08532) `evoprompt_ga` | 提示词种群 | 输入和标量适应度 | 锦标赛父代、交叉、变异和精英保留 |
| EvoPrompt DE `evoprompt_de` | 提示词种群 | 输入和标量适应度 | 不同的供体三元组、文本差异和目标替换 |
| [Self-Refine](https://arxiv.org/abs/2303.17651) `self_refine` | 指令资源 | 执行反馈和评审器 | 批评 → 修订 → 评估；将论文的输出细化思想适配到资源 |
| [ACE](https://arxiv.org/abs/2510.04618) `ace` | 经验手册 | 轨迹、分数和失败反馈 | 带稳定条目 ID 的反思器/策展器，以及经验证的新增/更新/删除增量 |
| [APE](https://arxiv.org/abs/2211.01910) `ape` | 指令池 | 任务示例和分数；参考可选 | 指令归纳、评分池和邻域采样 |
| [ProTeGi](https://arxiv.org/abs/2305.03495) `protesgi` | 指令束 | 失败小批量、反馈和分数 | 文本梯度和全分数束搜索 |
| [Bootstrap few-shot](https://arxiv.org/abs/2310.03714) `bootstrap_fewshot` | 追加到资源的示例 | 评估器接受的搜索执行成功案例 | 从运行中的应用收集通过案例的输入/输出对 |
| Few-shot random search `fewshot_search` | 示例子集与顺序 | 同一成功执行池 | 带留出选择的种子化子集/顺序搜索 |
| [MIPRO resource search](https://arxiv.org/abs/2406.11695) `mipro` | 指令和组件示例联合 | 任务、标量分数和成功的组件输入/输出轨迹 | 有依据的提议、轨迹自举和针对资源选择的分类 TPE |
| [PromptBreeder](https://arxiv.org/abs/2309.16797) `promptbreeder` | 任务指令和变异指令 | 种群适应度和反馈 | 共同进化有界任务/变异器种群；精简算子集 |
| [Reflexion](https://arxiv.org/abs/2303.11366) `reflexion` | 情景反思 | 失败轨迹和环境/评判器反馈 | 追加有界反思，同时保持基础指令固定 |
| [ExpeL](https://arxiv.org/abs/2308.10144) `expel` | 可复用洞见规则 | 带反馈的成功和失败经验 | 对比观察并更新引用实际搜索样本的规则 |

对于 **SkillOpt、Evo-Harness、AHE、Meta-Harness、RRSI、ADAS、DarwinX、ModularRSI 和 Arbor**，参见 [harness 搜索与方法策略](harness-search.md)。这些方法将进化扩展到技能、结构化设置、可执行代码和工作流图。

探索 [组件覆盖和即将推出的算法](evolution-components.md)，或 [添加你自己的优化器](optimizer-plugins.md)。

原始论文见 [研究参考](references.md#training-free-evolution)。

上游反馈假设和即将推出的集成契约，见 [方法要求指南](method-requirements.md)。

<a id="what-should-my-evaluation-set-look-like"></a>

## 我的评估集应是什么样？

EvoSprig 将应用评估转换为标量分数、书面反馈和执行观察。所有策略都可使用 [基于任务输入的 LLM-as-judge](evaluation.md)；只要存在客观环境检查，它们仍然有用。

| 应用 | 有用的输入/参考数据 | 有用的反馈粒度 |
| --- | --- | --- |
| 文档助手 | 问题、源文档、可选的引用参考答案 | 答案依据、引用检查、检索记录 |
| 软件团队 | 功能请求、验收标准、可丢弃的执行/浏览器环境 | 构建/测试结果、单个工具错误、最终应用行为 |
| Data Interpreter | 问题和表格/文件、可选的已知聚合值 | 数值检查、执行的代码、图表产物 |
| 支持或运维 | 客户请求、策略、沙箱状态、明确批准决策 | 策略合规性、工具参数和最终环境状态 |
| 写作或规划 | 简报、受众、约束和可选示例 | 基于评分标准的完整性、一致性和可用性 |
| 个人助理 | 任务输入和限定范围的种子事实；可选的多步沙箱会话 | 记忆更新、偏好使用和最终结果 |

示例方法至少需要一次成功的搜索执行。没有参考答案时，评审器可以验证该成功。当环境提供失败原因时，反思与洞见方法会提供更多信息。种群方法需要比短程细化循环更大的评估预算。

<a id="from-agent-to-improved-version"></a>

## 从 agent 到改进版本

在 Studio 中，配置任务集，选择资源和可选结构化字段，并选择算法。EvoSprig 会自动提出编辑并评估运行中的应用。结果视图将资源变更和配对输出一起显示。在 **Versions** 中审查并启用该版本。

使用 `Builder.skill(...)` 和 `node(..., skills=[...])` 附加可复用技能。完整设置见 [agent 配置](agent-resources.md)。

## 只进化一个节点或模块

在 **自进化工作台（Improve）** 中选择节点和模块，再配置任务集、算法、提出改动的模型与最大轮次。Prompt、skill 和代码资源可以单独选择；harness 和记忆参数直接填写搜索上下限；模型路由在应用声明的模型别名中搜索。多个字段一起搜索时，可展开高级搜索空间。

如果其他节点也使用同一份资源，平台会为选中节点创建独立副本；节点内的普通提示词会自动变成可进化资源。选择“整个应用”的资源模式时，修改会作用于所有引用该资源的节点。

```bash
evosprig improve my-agent/agent.yaml --suite my-agent/tasks.yaml \
  --method opro --target-node writer --target-module prompt \
  --rounds 8 --target-score 0.9 --patience 3 \
  --proposer-binding optimizer --profile my-agent/deployment.yaml
```

`--proposer-binding` 使用应用声明并在部署中配置的模型别名，省略时使用应用默认模型。CLI 可以重复传入 `--target-module` 选择多个模块。嵌套节点使用完整路径，例如 `/graph/nodes/team/branches/writing/nodes/writer`。

SDK 和 HTTP API 使用同一配置：

```python
from evosprig.evolution.study import StudyConfig

config = StudyConfig(
    method="opro",
    target={"node": "/graph/nodes/writer", "modules": ["prompt"]},
    rounds=8,
    goal={"score": 0.9, "patience": 3, "min_delta": 0.001},
    budget={"max_evaluations": 100, "max_model_calls": 200,
            "max_total_tokens": 200000, "max_seconds": 900},
    gate={"min_gain": 0.02, "min_samples": 2},
)
```

将 `config` 传给 `execute_study`，或将其 JSON 放在 API 请求的 `config` 中；API 的 `proposer_binding` 与 `config` 并列。目标分数按完整的 `selection` 任务集计算，小批量结果不会触发停止。`patience` 统计连续多少个不同候选没有超过 `min_delta` 的提升。停止搜索后继续执行独立的 release/test 验证，再由用户决定是否采纳。GEPA 的 `rounds` 同样限制变异迭代次数。

画布操作见[只进化团队中的一个智能体](tutorials/scoped-evolution.md)。

<a id="run-an-improvement"></a>

## 运行一次改进

```bash
evosprig improve my-agent/agent.yaml \
  --suite my-agent/tasks.yaml \
  --method protesgi --resource instructions \
  --rounds 2 --max-candidates 16 \
  --max-evaluations 100 --max-model-calls 200 \
  --profile my-agent/deployment.yaml
```

为 GEPA 安装 `pip install 'evosprig[evolution]'`。原生策略不需要额外的优化依赖。Studio 从后端注册表列出相同方法，并可创建仅输入套件、检查配对应用输出并比较资源差异。

每个候选都是其资源和 AgentSpec 的内容寻址快照。声明的搜索空间控制可编辑行为。部署权限、评估器和任务分区保持固定。`search` 任务指导提议；`selection` 提供验证；`release` 检查所选版本；可选的 `test` 任务在报告前保持封存。选择遵循所选方法的策略。

<a id="joint-instruction-and-demonstration-search"></a>

## 指令与示例联合搜索

```bash
evosprig improve my-agent/agent.yaml --suite tasks.yaml \
  --method mipro --resource instructions --rounds 3 \
  --instruction-candidates 3 --demo-candidates 3 --max-demos 2 \
  --demo-threshold 0.8 --max-candidates 16 --max-evaluations 100
```

MIPRO 资源搜索提出基于任务的指令，并从通过的搜索分片组件执行中收集实际输入/输出对。分类 TPE 采样器选择指令/示例联合组合。共享资源可以从使用它们的每个节点收集示例。当没有执行达到配置阈值时，示例保持为空。

此原生适配使用独立的分类密度和全分片评估，每轮最多四次联合试验。DSPy MIPROv2 提供不同的程序表示、更丰富的自举和小批量分配。候选存档记录所选组件轨迹和指令选择。在 CLI 或 Studio 中调整池大小、阈值和预算。

<a id="budget-inspect-and-release"></a>

## 预算、检查与发布

一次研究会限制评估、候选、模型调用、token 和耗时。任务、提议器和评审器调用都计入。搜索最初获得调用/token/时间上限的 60%；配对的发布/测试评估会被预留。验证可使用剩余额度。带用量回执的调用即使提供商截断响应也会计费；无用量回执的调用保留其预留。没有提供商账单数据时，货币成本未知。

报告保留实际输出、失败状态、工具/环境观察和用量。候选存档保留被拒绝的编辑和谱系。研究失去租约后，从已归档候选启动新研究。普通 agent 运行有自己的节点级恢复。

发布门禁检查配对质量、任务组回归、成功执行、样本数量和推理用量。审查 diff 和应用输出，然后手动启用版本。现有运行保留其原始版本；回滚会保留当前用户记忆。

自定义评分器、环境和比较导出见 [评估设置](evaluation.md)，具体结果见[应用画廊](../../examples/README.md)。
