[English](../support-matrix.md) · **简体中文** · [文档目录](README.md)

<a id="supported-capabilities"></a>

# 支持的能力

| 领域 | 可用 |
| --- | --- |
| 编写 | Python Builder、YAML/JSON AgentSpec 0.1/0.2/0.3、Studio 画布、嵌套可视化分组和子流编辑器 |
| 执行 | 模型/工具/智能体/代码节点、条件、汇合、有界循环、并行分支、动态映射、人工审批 |
| 持久化 | SQLite 检查点、租约防护、去重事件接收、外部作业、取消和操作协调 |
| 模型 | OpenAI 兼容文本、图像输入、结构化输出、工具和流式传输；按节点设置 temperature、top-p 和输出限制 |
| 智能体资源 | 主提示词和有序的可复用技能；独立资源搜索和共享资源编辑 |
| 工具 | Python、JSON HTTP、异步 HTTP 作业、MCP Streamable HTTP、只读 SQLite、ComfyUI 图和 Git 工作树；可选的 Python/WASM、浏览器、OCR 和本地图像/视频生成工具 |
| 记忆 | BM25、带排名融合的可插拔嵌入、上下文块、时间关系、情景/关联召回、来源感知摘要、多查询检索、按范围删除 |
| 共享工作区 | 带修订的文档、对等邮箱、智能体直发消息、可恢复等待和持久唤醒 |
| 进化 | 跨 21 个族系的 23 种免训练策略；提示词、技能、harness 参数、图、代码、路由和记忆搜索；自定义优化器注册；[方法矩阵](evolution.md) |
| 评估 | 搜索/选择/发布/测试分区；规则、JSON schema、LLM-as-judge、外部/复合评分器；输出/节点/轨迹/环境目标、并发隔离样本、IndustryBench 回放 |
| 版本 | 候选差异、谱系、手动发布、回滚和快照导出 |
| Studio | 英文和中文、嵌套画布、带保存执行输入的选中节点/分组调试、资源、历史、记忆、改进和发布 |
| 交付 | Python 源代码、独立 HTTP 服务、容器构建项目、经验证的 ZIP 导入 |
| 示例 | Episode Studio、Super-agent 仓库维护、VideoClaw 生产、CoworkOS 办公团队、机器人操作、数据分析、文档对话、研究、客户支持、个人记忆、软件团队、Python 分析、辩论、收据、会议、书籍、旅行、职业辅导、内容活动、互动学习、动态图形、行业助手和环境起草 |

默认服务器在单台主机上使用 SQLite 和有界异步工作进程。容器导出包含 Dockerfile；请在部署主机上使用 OCI 兼容工具构建它。原生 TypeScript 执行和多节点平台部署已在[路线图](roadmap.md)中。

视频制作通过共享作业契约连接图像/视频服务。可选的[本地 worker](../../apps/media-service)提供图像生成、参考条件控制、音频/转写检查以及影片组装。[ComfyUI 配方](comfyui.md)提供模型和适配器控制；[视觉节点](vision.md)审查生成的帧和片段。
