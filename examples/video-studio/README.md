# Video production studio

Build a [VideoClaw](https://github.com/HITsz-TMG/VideoClaw)-style production agent with EvoSprig. The application coordinates creative roles, assets, human reviews and asynchronous media tools.

<img src="../../docs/assets/video-workflow.svg" alt="Script, assets, parallel shots, review and composition" width="100%" />

## Workflow

1. A director model produces a typed script with characters, visual style and three shots.
2. An editor approves or changes the script before media jobs start.
3. The asset service creates a reusable character catalog.
4. Three branches generate a frame, pause for frame approval, then request a video clip using the approved frame and shared catalog.
5. An editor selects and orders clips, adds audio asset references and subtitles, and submits the timeline for composition.
6. A separate shot workflow regenerates one shot. Take history retains the original clip; selecting the new take updates only that shot. Recompose the edited timeline.

`agent.yaml`, `shot-agent.yaml` and `compose-agent.yaml` are portable AgentSpec projects. `build_agent.py` builds them with the SDK. `takes.py` stores immutable takes and revision-checked timeline selections.

## Run the orchestration demo

```bash
python -m pip install -e '.[server]'
python examples/video-studio/run_demo.py --workspace .evosprig/video-demo
```

The deterministic simulator returns `fixture://` asset references. The demo automatically answers review nodes, recreates the runtime after pauses, completes media jobs, retakes the middle shot and recomposes. `report.json` contains run IDs, old/new timeline selections and job counts. It does not create a video file.

## Connect generation tools

Implement the four bindings in `deployment.example.yaml` using your provider SDK or gateway. The orchestrator does not depend on a particular image/video vendor.

| Tool | Input | Output |
| --- | --- | --- |
| `media.assets` | Character descriptions and visual style | Catalog mapping each character ID to a reusable asset |
| `media.image` | Shot, visual style and character catalog | First-frame image asset |
| `media.video` | Shot, approved first frame and catalog | Video clip asset |
| `media.compose` | Ordered clips, audio assets and subtitles | Composed film asset |

Each endpoint follows the shared asynchronous job contract:

```text
POST /<tool>       Idempotency-Key: <operation id>  → {"job_id":"..."}
GET  /<tool>/<id>  → {"status":"pending"}
GET  /<tool>/<id>  → {"status":"succeeded","output":<typed result>}
DELETE /<tool>/<id> → cancel
```

An asset is `{ "id": "...", "uri": "...", "media_type": "image/png|video/mp4|audio/wav" }`. Provider-specific model names, credentials, task IDs and retries belong in the tool service. The service must preserve idempotency and reject a reused key with a different payload. Keep assets addressable across sessions. See [tool contracts](../../docs/tools.md).

VideoClaw supports providers including Wan, Seedance and Kling. This example adapts its staged production pattern; media adapters and generated film quality can be evaluated independently of workflow execution.

## Human review and retakes

Open the main project in Studio with its deployment profile. The History page exposes script, frame and timeline checkpoints. Review outputs are typed JSON; edit them before continuing.

For a retake, run `shot-agent.yaml` with the selected shot, existing catalog and visual style. Add the resulting clip to `TakeStore`, select it using the current timeline revision, then pass the ordered clips to `compose-agent.yaml`. Completed shots are reused. A changed script or character catalog should trigger explicit regeneration of affected shots.
