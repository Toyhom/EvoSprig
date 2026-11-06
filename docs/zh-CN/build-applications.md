[English](../build-applications.md) · **简体中文** · [文档目录](README.md)

<a id="build-an-agent-application"></a>

# 构建 Agent 应用

EvoSprig 应用由计算图、可编辑资源和部署绑定组成。同一个 AgentSpec 可在 Studio 中打开，也可通过 Python runtime 运行。

<a id="start-from-a-working-application"></a>

## 从可运行的应用开始

选择 [Episode Studio](../../examples/episode-studio) 制作动画故事，[Super-agent](../../examples/repository-agent) 处理仓库工作，[CoworkOS](../../examples/cowork) 用于协作团队，或选择更小的[示例](../../examples)。使用[快速入门](quickstart.md)安装 EvoSprig。

```bash
evosprig serve --project examples/cowork/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/cowork
```

打开 `http://127.0.0.1:18766`。配置模型连接，编辑请求并运行应用。

<a id="design-on-the-canvas"></a>

## 在画布上设计

1. 添加 **model** 节点用于单次生成，或添加 **agent** 节点用于可自行选择工具的模型。
2. 在节点检查器中附加提示词和可复用技能。设置输出 schema 和模型限制。
3. 添加 **tool** 节点以执行所需操作，例如 OCR、保存文件或合成视频。为 agent 提供工具允许列表，以限定其动态选择的操作。
4. 通过输入引用连接数据。使用 **parallel** 表示命名分支，使用 **map** 表示运行时创建的任务列表。
5. 添加 **human** 节点，由人工审核或编辑输出。使用循环执行有界修订周期。
6. 对相关节点分组；打开嵌套子流程以编辑其执行逻辑。保存并运行。

**History** 显示当前活动步骤和等待中的请求。响应审批以继续同一次运行。**记忆**管理智能体事实与工作上下文；**知识库**管理业务文档与检索。控件和键盘快捷键见 [Studio guide](studio.md)。

选择一个或多个节点，然后选择 **Debug selection** 测试该部分。填写生成的输入表单，或复用上次运行的输出。在 map 或重试循环内，选择已保存的项或 take 以恢复其输入和先前状态。已折叠的分组可以一起选择。调试运行使用与应用相同的模型、工具和权限。

对于图像和视频管线，[导入 ComfyUI 工作流](comfyui.md)，将其计算转换为可编辑的 tool 节点。

<a id="design-in-python"></a>

## 在 Python 中设计

将此内容保存为 `build_agent.py`，与 `prompts/draft.md` 和 `skills/style.md` 放在一起：

```python
from evosprig.sdk import Builder
from evosprig.core.spec import save_spec

text = {"type": "string"}
output = {"type": "object", "properties": {"text": text}, "required": ["text"]}
app = (
    Builder("writing-assistant",
            {"type": "object", "properties": {"brief": text}, "required": ["brief"]},
            output)
    .model("writer", "main")
    .resource("draft", "prompts/draft.md")
    .skill("style", "skills/style.md")
    .node("write", "model", model="writer",
          instructions={"resource": "draft"}, skills=["style"],
          inputs={"brief": {"ref": "input.brief"}},
          output_schema=output, max_output_tokens=2048)
    .output(text={"ref": "nodes.write.output.text"})
    .execution(max_total_tokens=12000)
    .build_spec()
)
save_spec(app, "agent.yaml")
```

运行 `python build_agent.py`，然后：

```bash
evosprig run agent.yaml --input '{"brief":"Draft a customer invitation"}'
evosprig serve --project agent.yaml --studio-dir apps/studio/dist
```

对于嵌入式执行，编译并运行同一规范：

```python
from pathlib import Path
from evosprig.config import make_models, make_tools
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal

workspace = Path(".evosprig")
version = compile_agent(app, Path("."))
runtime = Runtime(
    make_models(app), make_tools(workspace, Scope(app.id)),
    journal=SQLiteJournal(workspace / "runs.sqlite"),
)
result = await runtime.run(version, {"brief": "Draft a customer invitation"})
```

<a id="connect-tools-and-state"></a>

## 连接工具和状态

在应用中声明工具别名，并在[部署配置文件](tools.md)中配置 HTTP、MCP 或数据库绑定。内置[记忆](memory.md)和[共享文档工具](shared-workspaces.md)使用应用的工作区和身份。长时间任务实现 `ExternalTool`：提交、轮询和取消。runtime 会为其回执建立检查点，并在完成后恢复。

在计算图中使用 `allow_side_effects=True`，并对会保存文档或调用写入工具的运行使用 `--allow-writes`。

对于依赖请求的规则，将带有 `output_validator="check_plan"` 的有界 Python 代码资源附加到 model 或 agent 节点（spec 0.3）。其 `run(inputs)` 接收 `inputs["input"]` 和 `inputs["output"]`，并返回 `{"valid": bool, "feedback": str}`。图像输入字段会被省略。例如，验证生成的行程使用了请求的城市，或验证镜头引用命名了已声明的角色。使用 `output_errors="feedback"` 时，模型会收到未通过的规则，并在 `max_output_retries` 内修正其答案。Studio 在 **Application validation** 下提供此功能。

<a id="add-self-evolution"></a>

## 添加自进化

1. 将代表性请求放入 JSONL，每行一个输入对象。
2. 在 **Improve** 中导入这些输入并定义评估评分标准，或导入带参考、工具检查和环境结果的 [EvalSuite](evaluation.md)。
3. 选择已附加的提示词/技能资源和方法，然后设置预算。
4. 启动研究。检查资源 diff 和应用输出。
5. 在 **Versions** 中启用所选版本。

搜索可覆盖提示词、技能、代码资源、harness 设置、模型路由、记忆参数和工作流结构。请提前定义允许的搜索空间和评估任务。[Evolution components](evolution-components.md) 说明了组件映射。

<a id="ship"></a>

## 交付

使用[导出](deployment.md)生成独立的 Python、HTTP 应用或容器构建项目。通过环境变量绑定部署凭据，并将应用的数据加载到其工作区。
