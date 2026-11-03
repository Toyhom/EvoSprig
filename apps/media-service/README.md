# Local media tools

Run FLUX.2-klein-4B for character references and storyboard images, HunyuanVideo-1.5 for first-frame video generation, and FFmpeg for composition. Agents connect through ordinary HTTP tool bindings; model weights stay in the media worker.

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

The default address is `http://127.0.0.1:18880`. A single worker serializes GPU jobs. Each model family runs in a reusable child process; switching families releases the previous process and its GPU allocation. CPU offloading and tiled video decoding reduce GPU memory use. Keep the job database on a filesystem that supports SQLite locking.

Defaults are seed 42, 4 image steps, 12 video steps, 848 × 480 image pixels and 24 video frames per second. Change the seed, steps and image dimensions with CLI flags. Hunyuan selects a video resolution bucket from the first frame and its checkpoint configuration. The video backend supports first-frame generation for 1–15 seconds and silent composition; subtitle input uses SRT. Audio generation and first/last-frame conditioning need a different backend.

Use the model licenses supplied by [Black Forest Labs](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) and [Tencent Hunyuan](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5). Model weights are downloaded separately.

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
