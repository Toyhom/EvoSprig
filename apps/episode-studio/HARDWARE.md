# Hardware and model placement

Episode Studio uses **API models for its agents by default**. API calls need no local model VRAM. Local image and video tools have their own memory requirements; each agent can use a different [model connection](../../docs/model-connections.md).

## GPU capacity

The current weights are Qwen-Image-2.1 for images and the INT8 MiniMax H3 recipe for video. Their checkpoint sizes give useful planning bounds:

| Component | Weight files | Memory strategy |
| --- | ---: | --- |
| Qwen image transformer | 14.23 GB | Model or sequential CPU offload |
| Qwen image text encoder | 17.53 GB | Loaded for encoding, then offloaded |
| Qwen image VAE | 1.35 GB | Tiled decoding |
| H3 video transformer, INT8 | 20.97 GB | ComfyUI memory management and chunked feed-forward |
| H3 text encoder, INT8 | 26.36 GB | CPU placement in the low-VRAM preset |
| H3 video VAE, INT8 | 3.17 GB | Separate decode stage |

These components run in stages. VRAM also holds activations, attention buffers and temporary tensors; clip length, resolution and reference count change the peak.

| Device capacity | Image service | H3 video service |
| --- | --- | --- |
| 16 GB | Sequential offload and smaller images are the starting point | Requires aggressive offload or smaller quantized weights |
| 24 GB | Suitable target for CPU-offloaded generation | Low-VRAM preset: CPU text encoder, smaller render, chunking and partial model offload |
| 32–48 GB | More room for reference images and activations | More headroom for the standard recipe and longer clips |
| 80 GB | Server throughput and larger batches | Server throughput and larger batches |

This table is a capacity estimate from the pinned weights and execution paths. Production clips were generated on server GPUs; 16/24 GB end-to-end timings remain to be measured.

For host memory, plan **128 GB RAM** when retaining both image and video services and their CPU-offloaded weights. Fast local storage helps cold starts. Retaining a service keeps its loaded CPU state; lower-VRAM presets move layers between CPU and GPU as needed.

## Lower-memory preset

```bash
python3.12 apps/episode-studio/launch.py setup \
  --model-config .evosprig/episode/model-api.json \
  --memory-profile low-vram
```

This selects sequential image offload, tiled image VAE decoding, 1024×576 image defaults, CPU H3 text encoding, a 0.5-megapixel video base, four feed-forward chunks, and ComfyUI's low-VRAM mode. It writes an active recipe copy; the source recipe stays editable. `balanced` keeps the tuned production defaults. Advanced values remain editable in `services.json` and the render workflow.

The automatic launcher currently assigns image and video services to **separate GPUs** so independent workloads can overlap. Set `media_gpu` and `comfy_gpu` in `services.json` to the assigned device positions. A single card needs serialized image/video scheduling with explicit memory handoff; the launcher currently rejects overlapping device assignments. One-card coordination is the next deployment step.

## Model providers

Set `main` in `model-api.json` to your provider's base URL, model ID and credential environment variable. Add `vision` to use a separate multimodal reviewer; otherwise `main` handles both roles. OpenAI-compatible endpoints include OpenAI, Kimi, MiniMax, Qwen/DashScope and local vLLM. A text-only model can handle writing while a different model reads images.

In the canvas, use **Model connections** to register endpoints and **Model** on each node to assign them. Associate a local connection with a configured resident service to expose **Preload** on that node. The same mappings work in Python and standalone exports.

Sources: [Qwen-Image-2.1 weights and offload example](https://huggingface.co/Qwen/Qwen-Image-2.1), [H3 INT8 checkpoint](https://huggingface.co/smhfacct/Minimax-H3-fl2va-ref2va-hybrid-models), [ComfyUI memory management](https://github.com/Comfy-Org/ComfyUI), and the pinned [model manifest](models.json).
