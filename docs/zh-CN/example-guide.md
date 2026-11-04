[English](../example-guide.md) · **简体中文** · [文档目录](README.md)

<a id="contribute-an-application"></a>

# 贡献一个应用

向读者展示他们可以构建和使用的内容。通过 EvoSprig 的 SDK、AgentSpec 和运行时协调智能体。当应用需要时，添加可复用的框架能力。

```text
examples/my-application/
  README.md                  # Canvas, useful result, run command, customization
  canvas.png                 # The application's actual Studio canvas
  studio.json                # Saved layout and visual groups
  agent.yaml                 # Executable workflow
  prompts/                   # Role instructions
  skills/                    # Reusable procedures, when needed
  sample.json                # A task to try
  assets/                    # Only images and short media used by the README
  deployment.example.yaml    # Optional model and tool connections
```

以 README 的标题和 `![Workflow in EvoSprig Studio](../canvas.png)` 开头。在同一页面展示有用的结果：带简短说明的结果图片。随后说明如何运行应用以及读者可以自定义的内容。当构建脚本能够解释图构建过程时，它就有用。

当进化产生有用的变更时，在同一张图片中展示原始输出、实际提示词或技能编辑以及选定的输出。给出方法和任务上下文；数值比较需附上任务数量和评估器。否则，展示一个最终应用结果。保持每个应用页面自包含且简洁。

引用应用模式的来源以及命名方法背后的论文。连接真实的工具契约。在框架的测试套件中测试共享能力。

<a id="an-application-page-must-be-runnable-on-its-own"></a>

## 应用页面必须可独立运行

包括所需的 Python/Node 版本、检出和环境命令、依赖安装、确切的模型配置位置、端点/模型字段以及凭据环境变量。提供有效的首个输入和可执行的运行命令。记录所需服务及其安装/启动命令和端口、数据加载、写入权限、人工响应、输出位置，以及如何恢复或停止应用。

为已使用 EvoSprig 的用户包含画布入口以及导入/导出路径。链接到框架用于 SDK 开发的主要设置。对于标准应用，使用 `examples/quickstart.py`：在 `quickstarts.json` 中注册 spec/profile/data，并包含符合 schema 的示例输入。设置必须保留用户编辑。测试命令路径以及导出/导入往返；对于结构化应用，不要依赖通用 mock 响应。
