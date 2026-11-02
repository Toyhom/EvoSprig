# EvoSprig · 衍芽

Build agents that grow.

EvoSprig is an Apache-2.0 agent platform for building, running, evaluating and improving workflows, then exporting a selected version as a standalone application.

![EvoSprig Studio](docs/assets/studio.png)

用 Python 或画布构建智能体，在固定数据与预算下比较改进，再将选定版本导出为独立应用。

开源 Alpha 提供构建、持久运行、记忆检索、OPRO/GEPA、候选对比、版本启用与回滚，以及 Python / HTTP / 容器工程导出。Python 3.12+；Studio 源码构建需要 Node.js 20+。

```bash
git clone https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python -m pip install -e '.[server,evolution,mcp]'
evosprig run examples/hello/agent.yaml --input '{"question":"Hello"}' --mock
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --project examples/hello/agent.yaml --studio-dir apps/studio/dist --workspace .evosprig
```

打开 `http://127.0.0.1:18766`。真实模型凭据通过环境变量绑定，默认兼容接口使用 `deepseek-flash`。服务与运行状态保存在你指定的工作目录中。

- [快速开始 / Quickstart](docs/quickstart.md)：安装、画布、真实模型和独立导出。
- [研究助手](examples/research-assistant/README.md)：证据问答与工具调用，真实 OPRO / GEPA 对比。
- [18 秒短片](examples/short-film/README.md)：模型分镜、人工审核、异步渲染与进程重启恢复。
- [评测与进化](docs/evolution.md)：数据划分、共享预算、发布门槛和候选快照。
- [Studio 界面设计](docs/studio-design.md)：中性色布局、项目搜索、节点信息与移动导航。
- [自托管与导出](docs/deployment.md)、[支持矩阵](docs/support-matrix.md)、[架构](docs/architecture.md)、[验收记录](docs/validation.md)。

真实进化 smoke 中，两种方法均通过发布验证；保留测试集与人工基线没有分数提升。样本规模较小，结果用于验证工程闭环。短片为程序绘制的原创动态图形，分镜由真实模型生成。

采用 Apache-2.0；依赖和示例来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。开发维护入口为本仓库的测试、CI 与 [贡献指南](CONTRIBUTING.md)。

[开源范围](docs/open-source-scope.md) · [安全问题](SECURITY.md) · [后续路线](docs/roadmap.md)
