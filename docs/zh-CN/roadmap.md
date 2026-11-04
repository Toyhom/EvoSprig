[English](../roadmap.md) · **简体中文** · [文档目录](README.md)

<a id="roadmap"></a>

# 路线图

<a id="agent-capabilities-and-applications"></a>

## Agent 能力与应用

- 将仓库团队接入 issue 线程和经过审查的 pull request 交付；扩展网页导航、销售运营和长期运行的个人助理。
- 扩展 [skill 和 harness 优化器](harness-search.md) 的任务覆盖范围，添加持久化搜索续接，并支持并行分支 worker。
- 添加 TextGrad 组件反馈、完整的 DSPy MIPROv2 程序集成和 AFlow 工作流合成，置于显式执行环境之后。
- 添加 DGM 风格的 agent 代码进化和 AlphaEvolve 风格的程序搜索，具备隔离执行、正确性检查和版本归档。
- 发展经过验证的程序性技能库，遵循 Voyager 和 SkillWeaver 的可复用技能方向，且不进行模型权重训练。
- 添加记忆提供方绑定、自动笔记链接、巩固调度和冲突解决策略。
- 扩展剧集制作，加入场景级一致性评分、备选剪辑和更多媒体提供方。
- 添加更丰富的工件预览、评估表单、协同画布编辑和可复用子流模板。

<a id="server-deployment-and-portability"></a>

## 服务器部署与可移植性

- 分离 API 和 worker 进程，具备队列背压和 PostgreSQL 存储；以部署级准入限制扩展现有的按提供方 HTTP 池。
- 测量混合工作负载：同时进行的交互式运行、工具作业、评估和改进研究；根据测得的瓶颈调整并发。
- 添加按提供方的准入控制、公平调度和可观测性，使自托管部署能够高效使用服务器资源。
- 支持多节点 worker 和恢复，且不将应用与 Studio 耦合。
- 添加原生 TypeScript 执行、跨语言契约和经过验证的容器部署配方。

已实现的接口列在[支持矩阵](support-matrix.md)中。计划中的搜索和记忆方法在不进行模型权重训练的情况下运行。
