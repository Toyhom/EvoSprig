[English](../references.md) · **简体中文** · [文档目录](README.md)

<a id="research-references"></a>

# 研究参考文献

EvoSprig 的[进化方法](evolution.md)、[记忆](memory.md)和[工具使用](tools.md)所依据的原始研究。

<a id="training-free-evolution"></a>

## 免训练进化

| 方法 | 原始论文 | EvoSprig 用途 |
| --- | --- | --- |
| OPRO | Yang 等（2023），[Large Language Models as Optimizers](https://arxiv.org/abs/2309.03409) | 基于得分历史的提示提议 |
| GEPA | Agrawal 等（2025），[GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://arxiv.org/abs/2507.19457) | 官方反思式优化器适配器 |
| EvoPrompt | Guo 等（2023），[EvoPrompt: Connecting LLMs with Evolutionary Algorithms Yields Powerful Prompt Optimizers](https://arxiv.org/abs/2309.08532) | 遗传与差分提示搜索 |
| Self-Refine | Madaan 等（2023），[Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651) | 指令资源的评析/修订 |
| ACE | Zhang 等（2025），[Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models](https://arxiv.org/abs/2510.04618) | Reflector/curator playbook 更新 |
| APE | Zhou 等（2022），[Large Language Models Are Human-Level Prompt Engineers](https://arxiv.org/abs/2211.01910) | 指令归纳与邻域搜索 |
| ProTeGi | Pryzant 等（2023），[Automatic Prompt Optimization with “Gradient Descent” and Beam Search](https://arxiv.org/abs/2305.03495) | 文本梯度与束搜索 |
| Bootstrap demonstrations | Khattab 等（2023），[DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines](https://arxiv.org/abs/2310.03714) | 传入输入/输出演示与子集搜索 |
| MIPRO | Opsahl-Ong 等（2024），[Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs](https://arxiv.org/abs/2406.11695) | 原生联合指令/演示搜索，使用传入的组件轨迹和分类 TPE |
| PromptBreeder | Fernando 等（2023），[Promptbreeder: Self-Referential Self-Improvement Via Prompt Evolution](https://arxiv.org/abs/2309.16797) | 任务/变异指令协同进化 |
| Reflexion | Shinn 等（2023），[Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) | 基于失败轨迹的有界反思 |
| ExpeL | Zhao 等（2023），[ExpeL: LLM Agents Are Experiential Learners](https://arxiv.org/abs/2308.10144) | 从成功和失败经验中推导规则 |

| SkillOpt | [SkillOpt](https://arxiv.org/abs/2605.23904) | 有界锚定编辑、严格技能验证与慢速引导 |
| Evo-Harness | [Evo-Harness: Context-to-Harness Skill Compilation for Self-Evolving Agents](https://arxiv.org/abs/2608.15071) | 失败记忆编译与主题/通用技能发现 |
| AHE | [Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses](https://arxiv.org/abs/2604.25850) | 诊断、编辑清单、可度量归因与回滚 |
| Meta-Harness | [Meta-Harness: End-to-End Optimization of Model Harnesses](https://arxiv.org/abs/2603.28052) | 实现/轨迹归档与得分/token 前沿 |
| RRSI | [RRSI: Regularized Recursive Self-Improvement of Agent Harnesses](https://arxiv.org/abs/2609.24972) | 重复的得分/成本准入与正则化修订历史 |
| ADAS | [Automated Design of Agentic Systems](https://arxiv.org/abs/2408.08435) | 设计归档、自我评析与可执行候选 |
| DarwinX | [DarwinX: Evolving Agent Harnesses Through Natural Selection](https://arxiv.org/abs/2608.07545) | 分支重组与重复的保留并扩展检查 |
| ModularRSI | [ModularRSI: Modular and Generalizable Recursive Harness Self-Improvement](https://arxiv.org/abs/2609.14857) | 独立的目标自有分支、对比诊断与集成 |
| Arbor | [RUC-NLPIR/Arbor](https://github.com/RUC-NLPIR/Arbor)，假设树协调器与执行器 | 树扩展、剪枝、主干实验与向上洞察综合 |

实现策略与设置：[Harness 搜索](harness-search.md#method-policies)。

<a id="memory-retrieval-and-tool-use"></a>

## 记忆、检索与工具使用

| 机制 | 参考文献 | EvoSprig 用途 |
| --- | --- | --- |
| 相关性、重要性和新近性 | Park 等（2023），[Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) | 可配置的情景回忆排序 |
| 链接式记忆笔记 | Xu 等（2025），[A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110) | 显式笔记链接与来源感知摘要 |
| 可编辑上下文块 | Packer 等（2023），[MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) | 作用域上下文块与归档检索 |
| BM25 | Robertson 与 Zaragoza（2009），[The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019) | 词法排序 |
| 倒数排名融合 | Cormack、Clarke 与 Buettcher（2009），[Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods](https://doi.org/10.1145/1571941.1572114) | 多查询结果融合 |
| 多样性感知检索 | Carbonell 与 Goldstein（1998），[The Use of MMR, Diversity-Based Reranking for Reordering Documents and Producing Summaries](https://doi.org/10.1145/290941.291025) | 结果选择期间的词法相似度惩罚 |
| 迭代式工具使用 | Yao 等（2022），[ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) | 模型/工具观察循环 |
| LLM 评估 | Zheng 等（2023），[Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685) | 使用固定评分量规的任务评判，可选重复评分 |

应用数据与反馈契约见[方法要求](method-requirements.md)。

<a id="embodied-applications"></a>

## 具身应用

- **RAI** — Rachwał 等，*RAI: Flexible Agent Framework for Embodied AI*（2025）。[论文](https://arxiv.org/abs/2505.07532) · [代码](https://github.com/RobotecAI/rai)。[操作应用](../../examples/rai-manipulation)在 EvoSprig 中重现相机–推理–工具–反馈循环。

<a id="agent-runtime-design"></a>

### Agent 运行时设计

- [PenguinHarness](https://github.com/Prism-Shadow/penguin-harness)：紧凑工具集、上下文管理、后台会话和 agent 工作台为本地服务与工具观察工作提供了参考。
