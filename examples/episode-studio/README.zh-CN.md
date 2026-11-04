# Episode Studio

![EvoSprig 中的 Episode Studio 制作团队](assets/canvas.png)

[English](README.md) · 简体中文

**一段小说，一句想法，拍成你的下一部动画。**

把故事交给 Episode Studio。智能体团队完成剧本、角色与场景设定，生成参考图，逐镜拍摄，最后合成带对白和声音的影片。整支制作团队都可以在 EvoSprig 中修改。

[**作品展示 ↓**](#作品展示) · [**应用特性 ↓**](#应用特性) · [**开始制作 ↓**](#运行与实现)

## 作品展示

### 《少女薇拉的忧郁》· 开场片段

[![播放动画开场](assets/hillside.webp)](assets/hillside.mp4)

**两个朋友，一座小镇，以及山那边的世界。**

25 秒 · 中文对白与旁白 · **[有声播放](assets/hillside.mp4)**

改编自《原神》中的书籍[《少女薇拉的忧郁》第一卷](https://wiki.biligame.com/ys/少女薇拉的忧郁)。

## 应用特性

| 你提供 | 制作团队负责 |
| --- | --- |
| 小说或一句想法 | 风格、剧本、人设、场景和每个镜头的生成提示词 |
| 一套固定角色 | 跨镜头、跨集复用参考图、服装和音色 |
| 一个需要重拍的场景 | 检查画面、指出具体问题，在设定次数内自动重做 |
| 更长的故事 | 分镜制作、尾帧与动作衔接、带音轨的成片合成 |

### 自动检查画面，定向重拍

![视觉审核发现前景人物不对，自动修正首帧](assets/retake.jpg)

视觉编辑根据角色设定和分镜检查生成画面，发现问题后，把具体修改意见交给镜头导演，自动发起重拍。这个镜头中，系统恢复了薇拉的短发、蓝裙，以及她与萨奇的位置关系。

## 运行与实现

### 启动应用

![Episode Studio：输入故事，查看制作进度](assets/application.png)

```bash
python apps/episode-studio/launch.py setup --model-dir /path/to/models --env-root /path/to/environments
python apps/episode-studio/launch.py start
```

打开 **http://127.0.0.1:18767/episode/**，切换中文，粘贴故事，选择 **开始制作**。剧本、角色与镜头会逐步出现；完成后，在 **制作记录** 中播放影片。

通过 **打开画布** 修改智能体，使用 **调试所选节点** 单独尝试一个节点或一组流程。在 **打开渲染工作流** 中修改渲染节点，再导出到 ComfyUI。

**[安装、API 模型与国内镜像](../../apps/episode-studio/)** · **[ComfyUI 导入与导出](../../docs/comfyui.md)**

### 修改团队，接着拍下一集

修改[角色指令](prompts/)、[制作技能](skills/)和[渲染配方](../../apps/episode-studio/render-recipe.json)。渲染智能体保留调好的默认值，只修改当前镜头确实需要的参数；视频提示词采用 [MiniMax H3 官方范例](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)的写法。

将上一集输出的 `series` 传入新故事，继续使用同一套角色设定、参考图和音色。模型在制作之间保持常驻。[系列输入与部署设置](../../apps/episode-studio/#continue-a-series)。

希望这支团队越拍越好？打开 **改进**，选择 prompt、skill 或 harness 参数，提供场景任务和评价标准。已有[搜索空间](search-space.yaml)覆盖故事、美术、首帧检查和运动衔接。[配置评测任务](../../docs/evaluation.md)。
