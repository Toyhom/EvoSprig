# EvoSprig 文档

[English](../README.md) · **简体中文**

**跟着教程做一个应用，需要细节时查参考文档。**

## 入门教程

[学习路线](tutorials/README.md)从一个可运行的项目开始，逐步认识画布、代码、调试和自进化。每课都有明确产物和可自己尝试的修改。

1. [第一个智能体](tutorials/first-agent.md)：安装、运行、修改指令。
2. [十分钟开发漫画智能体](tutorials/comic-studio.md)：在画布上设计，调试单个分格，切换 Python。
3. [从画布到 Python](tutorials/canvas-to-python.md)：导出、独立运行、继续开发。
4. [用自己的任务改进智能体](tutorials/improve-an-agent.md)：评估、搜索、比较版本。

## 参考文档

按主题查找配置项、运行行为和扩展接口。

| 主题 | 文档 |
| --- | --- |
| 安装与应用结构 | [快速开始](quickstart.md) · [开发者指南](build-applications.md) · [架构与图](architecture.md) · [Python SDK 与完整 Schema](sdk.md) |
| 画布与节点设计 | [Studio](studio.md) · [提示词、技能与 harness](agent-resources.md) |
| 模型 | [全局默认与节点覆盖](model-connections.md) · [视觉与厂商参数](vision.md) · [预加载与 GPU 分配](local-models.md) · [模型来源](model-sources.md) |
| 工具与集成 | [工具和 MCP](tools.md) · [代码仓库工具](repository-tools.md) · [ComfyUI 导入导出](comfyui.md) |
| 记忆与协作 | [记忆](memory.md) · [共享文档与消息](shared-workspaces.md) |
| 评估 | [任务、评分与评委](evaluation.md) · [行业模拟环境](industry-environments.md) |
| 自进化 / RSI | [进化流程](evolution.md) · [可进化组件](evolution-components.md) · [Harness 与代码搜索](harness-search.md) · [算法数据要求](method-requirements.md) |
| 部署 | [导出与部署](deployment.md) · [持久运行与恢复](durable-runtime.md) · [事件触发](triggers.md) · [Episode 性能](episode-performance.md) |

## 扩展框架

[框架扩展指南](extend-framework.md) · [优化器插件](optimizer-plugins.md) · [应用样例规范](example-guide.md) · [开发环境](../../CONTRIBUTING.md)

[应用库](../../examples/README.md) · [支持接口](support-matrix.md) · [论文引用](references.md) · [路线图](roadmap.md)
