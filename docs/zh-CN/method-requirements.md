[English](../method-requirements.md) · **简体中文** · [文档目录](README.md)

<a id="match-evaluation-data-to-an-improvement-method"></a>

# 将评估数据与改进方法匹配

同一个应用任务可以支持多种优化方法。不同之处在于每种方法所消费的反馈。EvoSprig 的[评估契约](evaluation.md)提供分数、书面反馈、节点输出、工具回执和环境观察，而不要求固定的基准集合。

<a id="implemented-strategies"></a>

## 已实现的策略

| 方法族 / 策略 | 典型上游数据与反馈 | 向 EvoSprig 提供 |
| --- | --- | --- |
| OPRO | 示例和一个标量目标，通常是答案准确率 | 任务输入以及参考、评分器或 LLM 评判器 |
| GEPA | 训练/验证实例；标量分数和反思轨迹 | 不相交任务、指标和实际运行时观察；可选参考答案 |
| EvoPrompt GA / DE | 带标签的任务示例和种群适应度 | 带规则的 `expected` 值，或等效的任务特定评分器 |
| Self-Refine | 一个任务、一个初始输出和自然语言自我批评；标签并非必需 | 输入以及用于资源级适配的固定评估器 |
| ACE | 智能体轨迹、执行结果和用于 playbook 更新的反馈 | 环境/评判器反馈，附带工具观察和失败原因 |
| APE | 用于指令归纳的输入/输出演示；用于选择的似然或任务准确率 | 可用时使用配对参考；仅输入的归纳加评判器评分是原生适配 |
| ProTeGi | 由示例、预测和参考/错误反馈组成的小批量 | 参考或具体的评判器/环境反馈；文本梯度保留其源任务 |
| Bootstrap few-shot / random search | 训练示例、可选的教师轨迹，以及接受演示的指标 | 具有至少一次已评分成功执行的搜索任务；原生变体使用输入/输出演示 |
| MIPRO resource search | 基于任务的指令、成功的模块轨迹和标量程序分数 | 通过的搜索轨迹，带有已解析的节点输入/输出；指令/演示池大小和联合搜索预算 |
| PromptBreeder | 任务示例和用于任务/变异提示种群的适应度 | 输入加上稳定的标量评分，以及足够进行种群评估的预算 |
| Reflexion | 交互式任务尝试、观察和成功/失败信号 | 失败轨迹以及环境或评判器反馈；有界反思成为带版本的资源 |
| ExpeL | 成功和失败的经验，通常每个任务有多次尝试 | 带分数和原因的运行时经验；规则引用实际搜索样本 ID |

使用相同的固定评估标准比较候选版本。

<a id="skills-and-harness-evolution"></a>

## 技能与 harness 进化

[覆盖表](evolution-components.md#coverage-of-the-flashrsi-method-list)包含九种技能/harness 方法。它们的评估输入扩展了任务契约：

- **SkillOpt / Evo-Harness：** 任务流、执行轨迹、技能发现以及单独的验证任务。
- **AHE / Meta-Harness / RRSI：** 可编辑的 harness 文件、可复现的任务环境、执行轨迹、结果分数以及 token 或货币成本。
- **ADAS / DarwinX：** 可运行的候选设计、设计或分支存档，以及可重复的适应度测量。
- **ModularRSI：** 明确的模块归属、重复的同任务轨迹以及整个应用的集成检查。
- **Arbor：** 训练/验证任务执行、与假设关联的变更，以及用于洞见传播的实验结果。

LLM 评判器可以给定性输出评分。对于动作或代码变更，还应提供环境及其可观察结果。

<a id="other-training-free-directions"></a>

## 其他无需训练的方向

计划中的集成：

| 方向 | 所需输入/环境 | 集成工作 |
| --- | --- | --- |
| [TextGrad](https://github.com/zou-group/textgrad) | 任务输入、文本损失/评估器和可编辑变量图 | 将反馈路由到负责的组件 |
| 完整 [DSPy MIPROv2](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/mipro_optimizer_v2.py) | 训练/验证任务、可调用指标、指令和演示候选 | 原生资源搜索可用；上游 DSPy 程序绑定、教师自举和小批量分配仍待集成 |
| [AFlow](https://github.com/geekan/MetaGPT/tree/main/examples/aflow) | 可执行工作流算子、任务输入和评估环境 | 搜索会改变编排，因此必须验证拓扑和资源成本 |
| [Darwin Gödel Machine](https://github.com/jennyzzt/dgm) | 仓库任务、隔离的执行环境、测试和智能体变体存档 | 修改智能体实现需要代码级验证和可恢复的候选执行 |
| [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | 可执行程序、可验证目标和低成本的候选评估 | 程序进化需要沙箱执行和领域特定的正确性检查 |
| [Voyager](https://github.com/MineDojo/Voyager) | 交互式世界、观察、任务/课程反馈和可复用技能 | 技能成功取决于环境状态和动作效果 |
| [SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver) | 浏览器任务、页面观察、可执行技能和验证 | 在浏览器环境中执行并验证该过程 |

记忆策略有不同的契约。[Generative Agents](https://github.com/joonspk-research/generative_agents) 使用相关性、重要性和新近性；[A-Mem](https://github.com/agiresearch/A-mem) 组织和链接笔记；[Mem0](https://github.com/mem0ai/mem0) 和 [Graphiti](https://github.com/getzep/graphiti) 提供记忆提取/更新或时序知识机制。它们的写入路径需要事件、源元数据和范围；使用时有标签基准是可选的，应用特定的召回和结果检查衡量其收益。EvoSprig 的原生记忆策略及其边界列在[记忆指南](memory.md)中。

其关键步骤会更新模型权重的方法——例如 Toolformer 风格的工具使用训练或策略微调——不计入这一无需训练策略的计数。预训练的外部模型仍可作为模型、嵌入器或评估器接入。

<a id="choose-the-smallest-useful-contract"></a>

## 选择最小可用契约

- **写作与决策：** 输入、可选上下文、评分量规和 LLM 评判器。
- **检索：** 问题、文档集合、带来源信息的观察和依据检查。
- **代码与数据：** 任务输入、提供的文件、一次性执行环境和实际断言。
- **操作：** 初始沙箱状态、明确的批准响应、允许的动作和最终状态检查。
- **持久助手：** 种子记忆、会话身份和预期状态变化；多轮会话使用 SDK 环境。

使用 `Sample.context` 表示仅评估器可用的信息，使用 `Sample.expected` 表示参考，使用 `responses` 表示显式人工节点输入，并使用部署绑定表示服务。优化器不能用其自己的评分规则替代这些内容。

原始论文与实现映射：[研究参考](references.md)。
