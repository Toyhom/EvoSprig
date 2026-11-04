[English](../evolution-components.md) · **简体中文** · [文档目录](README.md)

<a id="what-can-evolve"></a>

# 哪些内容可以进化？

EvoSprig 会搜索带版本的应用资源和开发者选定的行为字段。配置任务集和搜索空间，然后选择 **跨 21 个方法家族的 23 种策略** 之一。

| 组件 | 搜索目标 |
| --- | --- |
| 提示词、过程与示例 | 附加文本资源；共享或按 Agent 区分 |
| 技能库 | 任务流发现、主题/通用过程和有界技能更新 |
| 结构化 Agent harness | 工具轮次、工具选择、并行读取、输出恢复和 token 限制 |
| 模型路由 | 在已声明的模型别名之间选择；采样参数 |
| 记忆与检索 | 检索工具、记录数、查询输入和上下文预算 |
| 工作流拓扑 | 节点、边、分支、有界循环和嵌套图 |
| 可执行代码 | 由已声明的代码工具执行的带版本 Python 资源 |

[配置 harness 搜索](harness-search.md)，可在 Python、CLI 或 Studio 中进行。候选版本同时包含资源差异和图差异，并随其选定行为导出。

<a id="coverage-of-the-flashrsi-method-list"></a>

## FlashRSI 方法列表的覆盖情况

目录现在包含 **SkillOpt、Evo-Harness、AHE、Meta-Harness、RRSI、ADAS、DarwinX、ModularRSI 和 Arbor**，以及 OPRO、GEPA、EvoPrompt 和 ACE。[方法策略](harness-search.md#method-policies) 描述每个原生实现，并链接到其原始工作。

<a id="other-algorithm-integrations"></a>

## 其他算法集成

| 方法 | 进化目标 | 集成工作 |
| --- | --- | --- |
| [TextGrad](https://github.com/zou-group/textgrad) | 多个文本变量 | 计算图反馈与变量级信用分配 |
| [DSPy COPRO](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/copro_optimizer.py) | 每个组件的指令 | 跨 Agent 资源协调搜索 |
| [DSPy SIMBA](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/simba.py) | 规则与演示 | 随机小批量、轨迹分析和候选选择 |
| [DSPy MIPROv2](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/mipro_optimizer_v2.py) | 程序、指令与演示 | 完整的上游程序适配器与 teacher/minibatch 控制；原生资源搜索可用 |
| [AFlow](https://github.com/geekan/MetaGPT/tree/main/examples/aflow) | 工作流算子与拓扑 | 算子搜索、有效图构建与执行预算 |
| [Darwin Gödel Machine](https://github.com/jennyzzt/dgm) | Agent 实现与工具 | 隔离代码编辑、功能任务与变体归档 |
| [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | 可执行程序 | 带可验证目标的程序搜索 |
| [Voyager](https://github.com/MineDojo/Voyager) | 可执行技能与课程 | 技能库、环境交互与复用检查 |
| [SkillWeaver](https://github.com/OSU-NLP-Group/SkillWeaver) | 可复用浏览器过程 | 浏览器技能合成、验证与检索 |

这些集成可使用结构化候选空间、执行工具和评估机制。[方法要求](method-requirements.md) 将每个方向映射到其输入与环境需求。

<a id="design-a-new-search-space"></a>

## 设计新的搜索空间

除指令外，有用的目标还包括模型路由、工具描述与发现、记忆提取与遗忘、检索查询与排序、上下文压缩、分解、角色分配、重试策略和可执行技能。同时衡量任务质量、延迟、模型/工具成本和失败率。评估标准和部署权限由开发者控制。

要为资源或结构化候选添加优化器，请使用 [插件接口](optimizer-plugins.md)。
