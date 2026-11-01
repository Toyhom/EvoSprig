# EvoSprig · 衍芽

Build agents that grow.

用 Python 或画布定义智能体，以相同规格运行并导出独立 Python 工程。

当前版本为 M0 开发原型。提供 AgentSpec 0.1、模型/只读工具/Agent 节点、运行预算与事件、兼容 API、Studio 编辑和 Python 导出。安装与使用见 [快速开始](docs/quickstart.md)，功能状态见 [支持矩阵](docs/support-matrix.md)。

```bash
python -m pip install -e '.[server]'
evosprig validate examples/hello/agent.yaml
evosprig run examples/hello/agent.yaml --input '{"question":"Hello"}' --mock
evosprig export examples/hello/agent.yaml --out ./hello-export
```

运行要求：Python 3.12+。Studio 构建使用 Node.js 20+。

模型凭据通过环境变量绑定。进化方法、持久恢复、长期记忆和视频应用按后续版本实现。
