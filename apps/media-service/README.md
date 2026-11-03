# Local media tools

Generate character references and storyboard images, animate shots and assemble the film. Choose FLUX.2-klein or Qwen-Image-2.1 for images, and HunyuanVideo or a [ComfyUI graph](../../docs/comfyui.md) for video. Agents connect through HTTP tool bindings.

The [video studio](../../examples/video-studio/) combines these tools with a director, visual frame review, human approvals and individual shot retakes.

## Start a worker

Use Python 3.10+ with a compatible CUDA PyTorch installation. The inference dependencies are separate from EvoSprig's lightweight runtime.

```bash
pip install -r apps/media-service/requirements.txt
hf download black-forest-labs/FLUX.2-klein-4B --revision e7b7dc27f91deacad38e78976d1f2b499d76a294 --local-dir models/flux2-klein
hf download hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_i2v_step_distilled \
  --revision 854c04a4c8a53d990b418c7478f0802c0fc8c726 --local-dir models/hunyuan-video

python apps/media-service/app.py \
  --image-model models/flux2-klein \
  --video-model models/hunyuan-video \
  --outputs outputs/media --database .evosprig-media/jobs.sqlite
```

The default address is `http://127.0.0.1:18880`. A single worker serializes GPU jobs. Each model family runs in a reusable child process; switching families releases the previous process and its GPU allocation. Idle models unload after 120 seconds, adjustable with `--idle-unload-seconds`. CPU offloading and tiled video decoding reduce GPU memory use. Keep the job database on a filesystem that supports SQLite locking.

Defaults are seed 42, 4 image steps, 12 video steps, 848 × 480 image pixels and 24 video frames per second. Change the seed, steps and image dimensions with CLI flags. Hunyuan selects a video resolution bucket from the first frame and its checkpoint configuration and generates 1–15 seconds per shot. Set `preserve_audio: true` when composing clips with sound; subtitle input uses SRT. Clips with different sizes or frame rates are normalized to the first clip's canvas at 24 fps, with silence added where an audio track is missing.

Use the model licenses supplied by [Black Forest Labs](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) and [Tencent Hunyuan](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5). Model weights are downloaded separately.

### Qwen images and ComfyUI video

Use Python 3.11+ and `requirements-qwen.txt` for Qwen-Image-2.1 generation and reference-guided editing. Its default is 40 steps. The [Qwen Research License](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE) permits noncommercial research; commercial deployment requires separate authorization.

```bash
pip install -r apps/media-service/requirements-qwen.txt
python apps/media-service/app.py \
  --image-backend qwen-image-2.1 --image-model models/qwen-image-2.1 \
  --comfy-input /path/to/ComfyUI/input --comfy-output /path/to/ComfyUI/output \
  --outputs outputs/media --database .evosprig-media/jobs.sqlite
```

The [episode team](../../examples/episode-studio/) stages generated references, renders through ComfyUI, then reads the actual frames and soundtrack. Inspection returns the beginning, middle and final frames, a closing clip, an audio reference and sound-level measurements. Voice references use up to four seconds by default; optional transcription locates the spoken section. Set `voice_seconds` between one and five to match your video model's reference budget.

For dialogue checks, install `requirements-speech.txt` and pass `--speech-model /path/to/faster-whisper-model`. Inspection adds a local CPU transcript with timestamps and confidence values; the continuity editor compares it with the planned lines.

## Connect an agent

Start Studio with `examples/video-studio/local-agent.yaml` and `deployment.local.yaml`. The profile uses `MOONSHOT_API_KEY` for Kimi K3.1 Pro and the local media endpoints below. Image inputs reach Kimi as base64 content parts. Visual checks use resized previews; generation uses the original assets.

| Endpoint | Function |
| --- | --- |
| `/assets` | Generate character references |
| `/image` | Generate a shot's first frame using its character references |
| `/video` | Animate an approved first frame |
| `/compose` | Join selected clips and optionally burn SRT subtitles |
| `/vision` | Read generated assets as bounded image inputs for a vision model |
| `/generate-image`, `/generate-video` | Lower-level generation for other applications |
| `/upload` | Import an image into the service's asset store |
| `/stage-reference` | Copy an image, video or audio asset to ComfyUI's input directory |
| `/ingest-comfy` | Collect ComfyUI's saved media |
| `/inspect-video` | Decode frames, extract continuity references and check audio levels |

Generation endpoints use `POST` with an `Idempotency-Key`, followed by `GET /<endpoint>/<job_id>`. `DELETE` requests cancellation. Reusing a key with different inputs returns 409. Completed results remain available after a restart. Retry an interrupted or failed take with `POST /jobs/<job_id>/retry`; its original inputs and job ID are preserved.

The service binds to loopback by default. Set `EVOSPRIG_MEDIA_TOKEN` and the matching tool `auth_env` when authentication is needed; listening on a non-loopback address requires this token. Use a secure tunnel or HTTPS reverse proxy for remote access.

## Use the same models with VideoClaw

`videoclaw.py` provides model/tool bindings for [VideoClaw](https://github.com/HITsz-TMG/VideoClaw). It adapts the LLM, vision, image and video provider entry points while keeping VideoClaw's workflow, agents and prompts. Run it from an environment containing the upstream backend dependencies:

```python
import sys
sys.path.insert(0, "/path/to/VideoClaw/video-claw/video-claw/backend")
sys.path.insert(0, "apps/media-service")
from videoclaw import LocalProviders

LocalProviders().install()
from core.orchestrator import WorkflowEngine
engine = WorkflowEngine()
```

Configure both upstream language-model fields as `kimi-k3.1-pro`, image fields as `FLUX.2-klein-4B`, and video fields as `HunyuanVideo-1.5`, using first-frame generation. The adapter uses the same worker settings and caps image/video requests. Keep the chosen adapter installed for the duration of that backend process.
