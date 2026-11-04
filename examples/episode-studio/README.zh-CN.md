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

需要 **Linux、Python 3.12、Node.js 20+、Git 和 NVIDIA CUDA 驱动**。API 导演方案使用两张 GPU 分别运行图像和视频工具；默认本地导演方案使用六张 80 GB GPU。可以先使用 API 导演：

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
mkdir -p .evosprig/episode
cp apps/episode-studio/model-api.example.json .evosprig/episode/model-api.json
export EPISODE_MODEL_API_KEY="你的 API Key"
python3.12 apps/episode-studio/launch.py setup --director api \
  --model-config .evosprig/episode/model-api.json \
  --model-dir "$PWD/models" --env-root "$PWD/.venvs"
python3.12 apps/episode-studio/launch.py start
```

安装器创建应用和模型环境、下载固定版本的权重，并构建画布编辑器。将 `--model-dir` 指向容量充足的模型磁盘，`--env-root` 指向环境目录。需要国内镜像时，在 setup 命令后加 `--mirror https://hf-mirror.com`。安装中断后，可以重复相同命令继续。

setup 前，编辑 `.evosprig/episode/model-api.json`。示例使用 `https://api.moonshot.cn/v1`、`kimi-k3.1-pro` 和凭据环境变量 `EPISODE_MODEL_API_KEY`，同时负责导演与视觉检查。若要分开设置，在 `main` 旁增加 `vision` 连接；视觉检查模型必须支持图片输入。每次在新终端 start 前都要设置相应凭据变量，启动器不自动读取 `.env`。

完全本地运行时，setup 改用 `--director local` 并去掉 `--model-config`。安装后可在 `.evosprig/episode/services.json` 修改 GPU 分配和端口。[models.json](../../apps/episode-studio/models.json) 列出了图像、视频模型来源。

打开 **http://127.0.0.1:18767/episode/**，切换中文，粘贴故事，选择 **开始制作**。剧本、角色与镜头会逐步出现；完成后，在 **制作记录** 中播放影片。

通过 **打开画布** 修改智能体，使用 **调试所选节点** 单独尝试一个节点或一组流程。在 **打开渲染工作流** 中修改渲染节点，再导出到 ComfyUI。

**[安装、API 模型与国内镜像](../../apps/episode-studio/)** · **[ComfyUI 导入与导出](../../docs/comfyui.md)**

### 停止和重新打开

```bash
python3.12 apps/episode-studio/launch.py status
python3.12 apps/episode-studio/launch.py stop
```

模型在制作之间保持加载；`stop` 停止当前会话的服务并释放显存。重新启动时复用同一个 state 目录，即可保留制作记录。若 **18767** 端口被占用，启动前修改 `services.json` 中的 `ports.app`。

### 导入已安装的 EvoSprig 继续开发

首次 start 后，模型和工具配置位于 `.evosprig/episode/deployment.yaml`：

```bash
evosprig serve --project examples/episode-studio/agent.yaml \
  --profile .evosprig/episode/deployment.yaml \
  --workspace .evosprig/episode-editor --studio-dir apps/studio/dist --port 18768
```

保持图像和 ComfyUI 服务运行，打开 **http://127.0.0.1:18768**，即可修改团队和调试节点。通过 **导出** 生成 Python 或 HTTP 应用 ZIP；在另一个 Studio 中使用 **导入项目** 继续编辑，并接回目标机器的模型、工具配置和媒体服务。[框架安装与 SDK 开发](../../README.zh-CN.md)。

### 修改团队，接着拍下一集

修改[角色指令](prompts/)、[制作技能](skills/)和[渲染配方](../../apps/episode-studio/render-recipe.json)。渲染智能体保留调好的默认值，只修改当前镜头确实需要的参数；视频提示词采用 [MiniMax H3 官方范例](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)的写法。

将上一集输出的 `series` 传入新故事，继续使用同一套角色设定、参考图和音色。模型在制作之间保持常驻。[系列输入与部署设置](../../apps/episode-studio/#continue-a-series)。

希望这支团队越拍越好？打开 **改进**，选择 prompt、skill 或 harness 参数，提供场景任务和评价标准。已有[搜索空间](search-space.yaml)覆盖故事、美术、首帧检查和运动衔接。[配置评测任务](../../docs/evaluation.md)。
