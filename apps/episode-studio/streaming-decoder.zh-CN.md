# 可选 H3 流式解码

[English](streaming-decoder.md) · [简体中文](streaming-decoder.zh-CN.md)

Episode Studio 可在视频解码阶段使用 [SolarX H3 Streaming VAE Decoder](https://github.com/SolarX-Team/H3-Streaming-VAE-Decoder)。它复用 ComfyUI 已加载的 H3 VAE，图像生成、扩散采样、音频和合成继续使用现有流程。

```bash
python apps/episode-studio/launch.py setup --model-config model-api.json \
  --model-dir /path/to/models --env-root /path/to/environments \
  --video-decoder streaming
python apps/episode-studio/launch.py start
```

安装固定上游版本 `a7c61a6e02bef8539178a17b6e150a775b3a0ebb` 及其补偿表，将 `EvoSprigH3StreamingDecode` 节点复制到本次部署的 ComfyUI。原配方不变，运行配方把 `VAEDecode` 替换为该节点并保留连线。设置 `--video-decoder standard` 可恢复默认。切换后重启自己的制作会话。

渲染画布可设置 `compensate`（默认开启）和 `token_budget`（默认 4096）。节点逐个解码潜变量，保留上游 K/V 窗口并报告进度，结束后向 ComfyUI 返回图像批次。这项优化作用于 VAE，不会把扩散模型变成可连续创作数分钟剧情的长视频模型；分镜时长、切镜、对白与衔接仍由制作图控制。

适配标准 MiniMax H3 视频 VAE，包括已有 ComfyUI INT8 加载方式。使用通用 PyTorch 路径，不要求 Blackwell 专属融合内核。空间分块越多，K/V 缓存越大，因此显存可能高于 ComfyUI 分块解码；按自己的分辨率和 GPU 选择，默认仍为标准解码。

已有 ComfyUI 可在其 Python 环境安装固定版本，将[自定义节点](comfy-nodes/evosprig_h3_stream/__init__.py)放入 `custom_nodes/evosprig_h3_stream/__init__.py`。节点使用原环境的 Torch 和 VAE 权重，CUDA/cuDNN 版本须保持匹配。
