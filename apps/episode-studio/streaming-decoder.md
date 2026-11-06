# Optional H3 streaming decode

[English](streaming-decoder.md) · [简体中文](streaming-decoder.zh-CN.md)

Episode Studio can use [SolarX's H3 Streaming VAE Decoder](https://github.com/SolarX-Team/H3-Streaming-VAE-Decoder) for the video decode stage. It reuses the H3 VAE already loaded in ComfyUI; image generation, diffusion sampling, audio and composition keep their existing paths.

```bash
python apps/episode-studio/launch.py setup --model-config model-api.json \
  --model-dir /path/to/models --env-root /path/to/environments \
  --video-decoder streaming
python apps/episode-studio/launch.py start
```

Setup pins the upstream decoder to `a7c61a6e02bef8539178a17b6e150a775b3a0ebb`, installs its compensation tables and copies the `EvoSprigH3StreamingDecode` custom node into this deployment's ComfyUI. The source recipe remains unchanged. The active recipe replaces `VAEDecode` with this node and retains the same links. Use `--video-decoder standard` during setup to restore the default. Restart your own production session after changing the setting.

The node exposes `compensate` (default true) and `token_budget` (4096) in the render canvas. It decodes one latent at a time, keeps the upstream K/V window and reports progress. ComfyUI receives an image batch when the node completes. This is a VAE optimization: it does not make the diffusion model generate an uninterrupted multi-minute story. Shot duration, camera cuts, dialogue and continuity remain controlled by the production graph.

The adapter supports the standard MiniMax H3 video VAE, including the existing ComfyUI INT8 loader. It uses the portable PyTorch path; Blackwell-only fused kernels are not required. K/V storage grows with spatial tile count, so streaming can use more memory than ComfyUI's chunked decoder. Select a mode using your resolution and GPU; the standard decoder remains the default.

For an existing ComfyUI installation, install the pinned package in its Python environment and copy [the custom node](comfy-nodes/evosprig_h3_stream/__init__.py) into `custom_nodes/evosprig_h3_stream/__init__.py`. The node uses that installation's Torch and VAE weights. Keep its CUDA/cuDNN packages mutually compatible.
