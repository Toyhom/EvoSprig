[English](../../tutorials/canvas-to-python.md) · **简体中文** · [学习路线](README.md)

<a id="move-from-canvas-to-python"></a>

# 从画布转向 Python

**目标：** 在编辑器中继续开发漫画工作流，并独立运行其导出的应用。

<a id="1-save-and-inspect"></a>

## 1. 保存并检查

在漫画项目中保存更改并打开 **Python**。找到模型定义、资源声明、节点输入和输出绑定。沿 `panels` 进入其 map 和 loop 主体。生成的 Builder 代码描述同一个已保存的 AgentSpec。

<a id="2-export-a-runnable-project"></a>

## 2. 导出可运行项目

在导出选择器中选择 **Python** 并下载 ZIP。将其解压到新目录。其中包含 `agent.yaml`、资源、运行时代码、`app.py` 和依赖项。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --profile deployment.yaml --input-file input.json --allow-writes
```

将部署配置和故事输入复制到此目录，设置其 API 密钥环境变量，并保持所引用的图像服务运行。导出智能体不会复制模型权重或凭据。

<a id="3-use-one-default-and-one-override"></a>

## 3. 使用一个默认项和一个覆盖项

使用 SDK 编写时：

```python
DEFAULT_MODEL = "writing-api"
builder.default_model(DEFAULT_MODEL, ["text", "structured_output"])
builder.model("vision", "local-vision", ["text", "structured_output", "vision"])
# A writer node can omit model= and use main.
# A reviewer sets model="vision" explicitly.
```

`main` 是共享别名。更改其部署绑定会更新使用它的所有节点，包括嵌套子流。显式的 `vision` 别名保留其自己的连接。[配置 GPU 放置和预加载](../local-models.md)。

<a id="4-return-to-studio"></a>

## 4. 返回 Studio

通过 **导入项目** 导入导出的 ZIP，选择项目 ID，并重新连接部署配置。更改后保存新的 ZIP。保留上一个可用版本，以便比较行为。

在仓库内进行源码开发时，编辑 [build_agent.py](../../../examples/comic-studio/build_agent.py)，运行它以重新生成 `agent.yaml`，然后在新的 Studio 项目中打开该 spec。[导入和导出契约](../deployment.md)。

**下一步：** [评估并改进智能体](improve-an-agent.md)。
