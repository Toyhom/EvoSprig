[English](../comfyui.md) · **简体中文** · [文档目录](README.md)

<a id="comfyui-tools"></a>

# ComfyUI 工具

导入 ComfyUI 工作流，将其工具连接到智能体，然后再次导出可编辑的工作流。模型、适配器、条件、采样和输出节点会保留各自的连接。Episode Studio 内含一个[渲染配方](../../apps/episode-studio/render-recipe.json)作为起点。

<a id="open-a-workflow"></a>

## 打开工作流

在 Studio 中，选择 **ComfyUI · Import workflow**，选择工作流 JSON 并输入 ComfyUI 服务器地址。**Check nodes and parameters** 会读取已安装的节点定义。选择 **Open on canvas** 创建项目。

选择 **Add a render node**，以便在运行时提交已组装的图。不勾选它，可在生成媒体前检查已准备好的图。

也可从 CLI 执行相同的导入：

```bash
evosprig comfy import workflow.json --server http://127.0.0.1:8188 \
  --id film-render --out film-render
evosprig serve --project film-render/agent.yaml \
  --profile film-render/deployment.yaml --studio-dir apps/studio/dist
```

离线导入接受来自 `/object_info` 的已保存响应：

```bash
evosprig comfy import workflow.json --schema object-info.json \
  --prepare-only --out film-render
```

<a id="edit-and-export"></a>

## 编辑并导出

选择工具节点以更改其输入。已连接的输入会跟随其源节点。使用 **Debug selection** 检查单个节点或一组节点，并带上已保存的上游值。准备运行会生成 JSON 图；渲染节点将其提交到 ComfyUI，并返回已保存的输出。

Studio 的 ComfyUI 导出会保留布局、备注、绕过状态和扩展元数据。其 API 形式包含可执行图。CLI 编辑使用一个小的补丁文件：

```json
{
  "12": {"inputs": {"steps": 14}},
  "8": {"enabled": false}
}
```

```bash
evosprig comfy export workflow.json --schema object-info.json \
  --patch changes.json --out edited-workflow.json
```

API 图也可以转换为可编辑的 ComfyUI 画布：

```bash
evosprig comfy export prompt.json --schema object-info.json \
  --format ui --out editable-workflow.json
```

连接、参数控件和固定种子会从已安装的节点定义中恢复。渲染失败会出现在运行事件中，并包含受影响的节点和服务消息；使用 **Debug selection** 检查修正后的输入。

<a id="let-an-agent-choose-parameters"></a>

## 让智能体选择参数

使用 `comfy_recipe` 绑定，公开已保存图中的所选控件。省略的控件保留图的默认值。每次调用都从该已保存图开始，因此某个镜头的设置不会泄漏到下一个镜头。

对于由上游滑块或 primitive 控制的值，公开该源节点的值。配方验证会在渲染前检查已连接的输入。

```python
from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

config = ComfyRecipeConfig(
    name="film.recipe",
    workflow=workflow_json,
    object_info=installed_node_schemas,
    outputs=["save_video"],
    parameters={
        "steps": {"node_id": "sampler", "input_name": "steps",
                  "schema": {"minimum": 12, "maximum": 16}},
        "action": {"node_id": "action_lora", "kind": "enabled"},
    },
    reference_slots=[{"node_id": "character_image"}],
)
tool = comfy_recipe_tool(config)
prepared = await tool.invoke({
    "controls": {"steps": 14, "action": True},
    "reference_images": ["generated-character.png"],
})
```

参考图像必须已在 ComfyUI 输入目录中。[媒体服务](../../apps/media-service)可以将生成的资产暂存到那里。未使用的参考槽会断开连接。使用单独的 `comfy_job` 绑定来渲染 `prepared["prompt"]`；其 submit/poll/cancel 生命周期使用常规运行时日志。

对于视听工作流，将 `audio_slots` 和 `video_slots` 与每个加载器的 `node_id` 和 `input_name` 一起声明。调用可接受 `reference_audio` 和 `reference_videos`，并与 `reference_images` 一起使用。在 `enabled` 参数上使用 `also_nodes`，以一起切换整条适配器链。单个节点的显式切换会覆盖组切换，因此智能体可以选择预设并调整各个适配器。

在 `kind: comfy_recipe_info` 下用单独的工具名称公开相同配置，以便智能体读取其控件和已保存默认值。该只读工具返回 `controls`（JSON Schema）、`defaults` 和 `reference_limits`。[剧集团队](../../examples/episode-studio)使用这些值选择 LoRA 强度、采样和放大设置。其输出验证器在提交渲染前检查建议的控件。

对于专用 ComfyUI 进程，设置 `dedicated: true` 以允许中断和模型卸载。共享实例支持取消排队中的作业。在考虑另一次渲染前，丢失的提交响应会与队列/历史记录进行核对。

<a id="edit-the-full-render-graph"></a>

## 编辑完整渲染图

带有配方绑定的应用会在 Studio 中公开 **Open render workflow**。该视图包含加载器、参考、采样、适配器、路由、备注和已绕过的节点。搜索节点以聚焦它，编辑其类型化参数，保存，或导出完整的 ComfyUI 文档。已保存的配方更改属于所选项目，并应用于其下一次运行。正在运行的作业保留其已保存的绑定。已有画布的工作流保留其布局；API 图按依赖关系排列。

<a id="large-graphs"></a>

## 大型图

每个图最多支持 512 个节点。导入的计算节点传递小型连接句柄，并在提交前组装一次渲染图。其参数计算是确定性的，因此中断的计算可以再次运行。模型请求和外部渲染提交会保留各自独立的持久操作记录。

`execution.pure_checkpoint_interval` 控制多少个纯计算可以共享一个检查点。其默认值为 `1`；ComfyUI 导入会选择 `16`。运行时还会在外部操作前、挂起时以及运行结束时刷新这些计算。导入会根据图大小调整其执行截止时间；这两项设置都可在规范中编辑。
