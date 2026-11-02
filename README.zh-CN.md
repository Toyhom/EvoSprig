<div align="center">

<img src="docs/assets/hero.svg" alt="EvoSprig · 衍芽" width="880" />

**构建智能体，用评测驱动改进，交付可独立运行的应用。**

[![CI](https://github.com/Toyhom/EvoSprig/actions/workflows/ci.yml/badge.svg)](https://github.com/Toyhom/EvoSprig/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](README.md) · **简体中文**

[快速开始](docs/quickstart.md) · [案例库](examples/README.md) · [自进化](docs/evolution.md) · [文档](docs/README.md)

</div>

EvoSprig 将可视化工作流、持久记忆和评测驱动的自进化放在同一个智能体开发平台中。用 Python 或 Studio 构建，在自己的任务上比较候选版本，再导出独立应用。

<img src="docs/assets/studio.png" alt="EvoSprig Studio 工作流画布" width="100%" />

## 可以构建什么？

| 应用 | 试着让它做什么 |
| --- | --- |
| **[数据分析助手](examples/data-analyst/)** | “哪个地区增长最快？”直接提问，查看数据结果和查询 SQL。 |
| **[文档问答](examples/document-chat/)** | 把团队手册、会议记录和产品资料变成带来源的回答。 |
| **[调研团队](examples/research-team/)** | 拆分一个大问题，分工查资料，整理成由你审阅的报告。 |
| **[视频工作室](examples/video-studio/)** | 从创意到剧本、分镜、视频和合成，接入自己的媒体工具，随时重做某个镜头。 |
| **[客服助手](examples/customer-support/)** | 查询订单、回答客户问题，由人工确认退款。 |
| **[个人助手](examples/personal-memory/)** | 记住偏好，在下次会话中继续使用。 |

打开 **[案例库](examples/README.md)**，选一个模板，开始开发自己的应用。每个模板都由 EvoSprig 的 SDK、AgentSpec 和运行器执行。

## 核心能力

- **代码与画布共用一套规格**：Python Builder、Studio、条件分支、循环、并行协作与人工节点。
- **可评测的自进化**：OPRO、GEPA、EvoPrompt GA/DE、Self-Refine、ACE；保留候选差异、评测、血缘与预算。
- **有来源的持久记忆**：BM25、可插拔语义检索、上下文块、时序关系及用户作用域。
- **可恢复的执行**：检查点、外部任务 ID 与幂等键支持重启、审核和长任务恢复。
- **独立交付**：导出 Python、HTTP 服务或容器构建工程，运行时无需连接 Studio。
- **模型与工具扩展**：兼容模型 API、Python、HTTP 与 MCP。

## 快速开始

需要 **Python 3.12+**，Studio 构建还需要 **Node.js 20+**。

```bash
git clone https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python -m pip install -e '.[server,evolution,mcp]'
evosprig run examples/hello/agent.yaml --input '{"question":"你好"}' --mock
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --project examples/hello/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig
```

打开 **http://127.0.0.1:18766**，在侧栏选择 **中文**；浏览器会记住语言设置。真实模型使用环境变量和[部署配置](examples/deployment.example.yaml)。

## 改进你的智能体

准备应用需要处理的任务，选择允许改进的提示词或技能，在 Studio 中比较候选版本。可以使用 OPRO、GEPA、EvoPrompt GA/DE、Self-Refine 或 ACE，审阅结果后启用新版本。[自进化指南](docs/evolution.md)介绍完整用法。

## 参与开发

欢迎提交问题、案例与集成，开发和检查方式见[贡献指南](CONTRIBUTING.md)。

## 许可证

[Apache-2.0](LICENSE)。
