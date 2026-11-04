[English](../model-sources.md) · **简体中文** · [文档目录](README.md)

<a id="model-sources"></a>

# 模型来源

EvoSprig 的源代码采用 Apache-2.0 许可证。模型权重、外部运行时和随附资源保留各自的许可证。安装程序从上游仓库将权重下载到用户机器；EvoSprig 仓库包含源代码和下载引用。

| 组件 | 上游来源与条款 |
| --- | --- |
| 剧集导演 | [Qwen3.8-Flash-Next FP8](https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8) · [许可证](https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8/blob/main/LICENSE) |
| 角色与场景图像 | [Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1) · [Qwen Research License](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE)：研究与评估；商业使用需另行授权 |
| 语音参考 | [Qwen3-Omni Instruct](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct) · [许可证](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct/blob/main/LICENSE) |
| 对话转写 | [Faster Whisper large-v3-turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo) |
| 备用图像后端 | [FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) · [Apache-2.0](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/main/LICENSE.md) |
| Hunyuan 视频 | [HunyuanVideo-1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5) |
| H3 视频与音频 | [MiniMax H3](https://huggingface.co/Comfy-Org/MiniMax-H3) · 所选检查点和适配器位于[部署清单](../../apps/episode-studio/models.json) |
| 工作流执行 | [ComfyUI](https://github.com/Comfy-Org/ComfyUI) 以及部署清单中锁定的扩展 |

每个模型卡是其使用条件的依据。应用可通过相同的模型和媒体工具接口替换这些提供方。
