# Model sources

EvoSprig's source code is licensed under Apache-2.0. Model weights, external runtimes and supplied assets retain their respective licenses. Installers download weights from the upstream repositories to the user's machine; the EvoSprig repository contains source code and download references.

| Component | Upstream source and terms |
| --- | --- |
| Episode director | [Qwen3.8-Flash-Next FP8](https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8) · [license](https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8/blob/main/LICENSE) |
| Character and scene images | [Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1) · [Qwen Research License](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE): research and evaluation; commercial use requires separate authorization |
| Voice references | [Qwen3-Omni Instruct](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct) · [license](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct/blob/main/LICENSE) |
| Dialogue transcription | [Faster Whisper large-v3-turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo) |
| Alternative image backend | [FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) · [Apache-2.0](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/main/LICENSE.md) |
| Hunyuan video | [HunyuanVideo-1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5) |
| H3 video and audio | [MiniMax H3](https://huggingface.co/Comfy-Org/MiniMax-H3) · selected checkpoints and adapters in [the deployment manifest](../apps/episode-studio/models.json) |
| Workflow execution | [ComfyUI](https://github.com/Comfy-Org/ComfyUI) and the extensions pinned in the deployment manifest |

Each model card is the source for its usage conditions. Applications can replace these providers through the same model and media-tool interfaces.
