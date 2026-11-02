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

| 应用 | 工作流 |
| --- | --- |
| **[视频制作工作室](examples/video-studio/)** | VideoClaw 类型的流程：剧本 → 角色资产 → 并行镜头 → 分镜审核 → 视频任务 → 剪辑 → 合成；支持单镜头重做。 |
| **[研究团队](examples/research-team/)** | 检索证据，分析师与质疑者并行工作，作者整理带引用的报告，编辑审核。 |
| **[客服助手](examples/customer-support/)** | 查询订单、提出处理方案、人工审核、幂等退款；拒绝后不会执行退款。 |
| **[个人记忆助手](examples/personal-memory/)** | 跨会话保存偏好，结合上下文块、当前事实与关系历史回答问题。 |
| **[自进化研究助手](examples/research-assistant/)** | 工具调用与证据问答，优化指令，比较候选版本后启用。 |

安装方法、运行入口和适配说明统一放在 **[案例库](examples/README.md)**。视频案例采用可替换的异步工具协议，内置模拟器验证编排，不生成媒体。

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

## 改进智能体

```bash
evosprig improve examples/research-assistant/agent.yaml \
  --suite examples/research-assistant/suite.yaml \
  --method self_refine --resource instructions --rounds 3 \
  --profile examples/deployment.example.yaml --workspace .evosprig
```

搜索、候选选择、发布验证与测试报告使用独立数据划分。在 Studio 比较资源差异和分数，再启用或回滚版本。[方法说明](docs/evolution.md)。

## 参与开发

欢迎提交问题、案例与集成，开发和检查方式见[贡献指南](CONTRIBUTING.md)。

## 许可证

[Apache-2.0](LICENSE)。
