[English](../../tutorials/comic-studio.md) · **简体中文** · [学习路线](README.md)

<a id="ten-minutes-to-a-comic-agent"></a>

# 十分钟构建漫画智能体

[![第一期：漫画工作室](../../tutorials/assets/comic-01.jpg)](../../tutorials/assets/comic-01.mp4)

**[观看十分钟教程](../../tutorials/assets/comic-01.mp4)** · 中文字幕 · [导入课堂工程](../../tutorials/assets/comic-project.zip)

| 时间 | 内容 |
| --- | --- |
| 00:12 | 看懂四步工作流 |
| 00:58 | 全局默认模型与连接 |
| 01:44 | 编剧提示词、连续性技能与 harness |
| 03:16 | 输入故事，真实运行编剧节点调试 |
| 04:25 | 共享角色参考、map 与重画循环 |
| 05:57 | 分格导演、绘图工具与视觉审核 |
| 07:29 | 传递反馈、查看历史、排版成页 |
| 08:38 | 切换 Python 并导出 |
| 09:24 | 漫画成品 |

课堂工程包含视频中编辑的中文提示词。在 Studio 中导入 ZIP，或解压后按照其中的 README 运行。复制 `deployment.example.yaml` 为 `deployment.yaml`，配置文本和视觉模型，再提供故事 JSON 和下方说明的图像服务。

**目标：** 在画布上自定义一个完整的漫画应用。你将编辑编剧、共享角色参考、分镜循环和视觉审核，然后打开 Python 视图。

从[可用的 Comic Studio 模板](../../../examples/comic-studio)开始。其图像和页面布局工具已连接，因此本课重点在智能体设计。使用示例的 **Run** 部分安装并配置它，包括一个多模态审核器和一个正在运行的图像服务。然后打开：

```bash
python examples/quickstart.py comic-studio studio --port 18766
```

<a id="1-read-the-four-part-workflow"></a>

## 1. 阅读四部分工作流

主画布上依次为 **adapt → cast → panels → pages**。`adapt` 将故事转换为结构化计划。`cast` 准备共享角色参考。`panels` 为每个分镜运行一个子流程。`pages` 排布图像和文字。

使用 **Arrange** 适配图形。打开嵌套的 `panels` 工作流，而不是一次性展开所有实现细节。

<a id="2-set-one-model-for-the-team"></a>

## 2. 为团队设置一个模型

打开 **Model connections**，输入你的提供商 URL、模型 ID 和 API-key 环境变量，然后保存连接。将其选为 **Application default model**。使用 `main` 的节点共享此选择。

视觉审核器使用 `vision` 连接。在该节点上选择它并启用图像输入。一个多模态模型可以同时承担这两个角色；文本模型和单独的视觉模型也可以。

<a id="3-give-the-writer-an-output-contract"></a>

## 3. 为编剧提供输出契约

选择 `adapt`。阅读其提示词和 `continuity` 技能。将故事方向改为一个四格漫画，具有清晰的开端、转折和结局。保留输出字段：title、style、characters 和 panels。每个 panel 包含 camera、characters、description、caption 和 dialogue。

在 harness 中，保持启用结构化输出反馈并限制重试次数。运行前保存。尝试一个短故事：一个孩子把蓝色雨伞借给年长的邻居；学习时保持角色阵容较小。

<a id="4-keep-references-shared"></a>

## 4. 保持参考共享

选择 `cast`。这是一个必需的工具步骤：工作流始终准备角色目录。其输出传递到分镜子流程。智能体决定角色描述；工具执行图像工作。

在计划中更改某个角色的服装，并跟踪其参考 ID 如何到达每个分镜。这里是进行全角色阵容更改的地方。

<a id="5-open-the-panel-and-retake-loops"></a>

## 5. 打开分镜与重拍循环

打开 `panels`，然后打开 `takes`。内部顺序为 **direct → draw → preview → review → remember**。导演编写图像提示词；图像工具绘制；preview 使画面可供审核器使用。审核器返回 `accepted` 和具体的 `feedback`。

编辑导演的提示词，以指明该分镜的 camera 和 action，并复用提供的角色参考。测试时将循环保持为三次尝试。下一次尝试会接收上一次反馈；验收通过会提前停止循环。

<a id="6-debug-one-panel"></a>

## 6. 调试一个分镜

保存。使用 **History**，打开一个已完成分镜的步骤，并选择 **Debug with these inputs**。运行前检查选中的 map 项和循环迭代。你可以更改导演或审核器，并使用其保存的输入重试该部分。

对于没有历史记录的新项目，先选择 `adapt`，并使用故事输入执行 **Debug selection**。在花费图像生成时间之前检查其计划。

<a id="7-make-the-page-then-open-python"></a>

## 7. 生成页面，然后打开 Python

返回主工作流。`pages` 接收分镜图像、说明文字和对白，并生成 PDF、图像和可编辑 HTML。使用 **Live models** 和 **Allow configured write tools** 运行。工作进程在后台跟踪图像任务。

保存后打开 **Python**。这些是相同的节点、资源、模型绑定和循环。使用 **Export → Python** 在编辑器中继续。

![完成的四格漫画](../../../examples/comic-studio/assets/page.jpg)

<a id="try-it-yourself"></a>

## 自己动手试试

更改故事和一个角色特征。保留输出契约、共享参考流程和审核循环。比较计划与生成的分镜，然后调整负责该问题的最小角色。

**下一步：** [从画布转到 Python](canvas-to-python.md)。查阅：[节点资源](../agent-resources.md)、[Studio 调试](../studio.md)、[模型服务](../local-models.md)。
