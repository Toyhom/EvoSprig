# VideoClaw (EvoSprig)

![Production workflow in EvoSprig Studio](canvas.png)

An EvoSprig reproduction of [VideoClaw](https://github.com/HITsz-TMG/VideoClaw). Turn a story idea into a short film: plan the scenes, create the characters, generate the shots and assemble the cut.

## Short films

<table>
<tr>
<td align="center" valign="top" width="33%"><a href="assets/moon-garden.mp4"><img src="assets/moon-garden.webp" width="100%" alt="Play Moon Garden" /></a><br><b>▶ Moon Garden</b><br>A robot grows a garden on the moon.</td>
<td align="center" valign="top" width="33%"><a href="assets/last-library.mp4"><img src="assets/last-library.webp" width="100%" alt="Play The Last Library" /></a><br><b>▶ The Last Library</b><br>One book lights up the night.</td>
<td align="center" valign="top" width="33%"><a href="assets/cloud-bakery.mp4"><img src="assets/cloud-bakery.webp" width="100%" alt="Play Cloud Bakery" /></a><br><b>▶ Cloud Bakery</b><br>A cat opens a bakery in the clouds.</td>
</tr>
</table>

## Run it

### Install

Use **Python 3.12+** and Git. Run these commands in Bash (Linux, macOS or WSL):

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install '.[server]'
```

Keep subsequent commands in this checkout, with `.venv` activated.

### Configure the model

```bash
python examples/quickstart.py video-studio setup
export MOONSHOT_API_KEY="your-api-key"
```

The application uses **`kimi-k3.1-pro`** at **`https://api.moonshot.cn/v1`**. Its settings are in `.evosprig/examples/video-studio/deployment.yaml`: change `base_url`, `model` and `api_key_env` under `models` to use another OpenAI-compatible endpoint. When changing providers, also remove or update provider-specific `options`, `token_limit_field` and `send_sampling_parameters` in that connection. Set the environment variable named by `api_key_env` in each terminal that starts or resumes the app. API keys are read from that variable; `.env` files are not loaded automatically.

Setup also creates `.evosprig/examples/video-studio/input.json` from the included [sample.json](sample.json). Edit this input for your task. Repeating setup preserves your profile and input.

### Start the local image and video tools

Use Linux and an NVIDIA CUDA GPU. The worker uses CPU offloading and tiled video decoding; provision GPU and host memory for the selected checkpoints and clip size. In a second terminal, create a separate Python 3.12 environment for inference:

```bash
python3.12 -m venv .venv-media
source .venv-media/bin/activate
python -m pip install torch==2.8.0 torchvision==0.23.0
python -m pip install -r apps/media-service/requirements.txt
hf download black-forest-labs/FLUX.2-klein-4B \
  --revision e7b7dc27f91deacad38e78976d1f2b499d76a294 --local-dir models/flux2-klein
hf download hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_i2v_step_distilled \
  --revision 854c04a4c8a53d990b418c7478f0802c0fc8c726 --local-dir models/hunyuan-video
python apps/media-service/app.py \
  --image-model models/flux2-klein --video-model models/hunyuan-video \
  --outputs outputs/media --database .evosprig-media/jobs.sqlite --preload image
```

For a domestic download mirror, set `HF_ENDPOINT=https://hf-mirror.com` before `hf download`. For gated weights, accept access on the model page and run `hf auth login` first. Leave the worker running at **http://127.0.0.1:18880**; generated media stays under `outputs/media`. The director and frame reviewer use the vision-capable API model configured above. Change `tools` endpoints to connect another media worker.

### Run a task

```bash
python examples/quickstart.py video-studio run --allow-writes
```

The assembled MP4 is returned as a media asset with a download URL. Runs and checkpoints stay in `.evosprig/examples/video-studio`. To use a separate input file, append `--input-file /path/to/task.json`.

The workflow pauses for script, shot and timeline review. Use **History** in Studio to inspect the proposed data and submit the matching response form. The per-shot review lets you request a replacement while keeping the other shots.

### Open the canvas and keep developing

Install **Node.js 20+** and build the editor once:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py video-studio studio
```

Open **http://127.0.0.1:18766**, select **Live model** and paste `input.json` into Run. Enable **Allow writes** for this workflow. Use **History** to inspect steps and respond to review/input requests. Change the port with `--port 18768` if needed.

This loads the application into your Studio workspace. Edit its prompt, skill, model and tool settings on the canvas; use **Debug selection** to try a node or group. The same workflow is defined in [local-agent.yaml](local-agent.yaml). For framework installation and SDK development, see [Get started](../../README.md#get-started).

<details>
<summary>Import into another EvoSprig workspace or export an independent application</summary>

```bash
python examples/quickstart.py video-studio pack --out .evosprig/video-studio.zip
evosprig import .evosprig/video-studio.zip --out .evosprig/imported-video-studio
evosprig serve --project .evosprig/imported-video-studio/agent.yaml \
  --profile .evosprig/examples/video-studio/deployment.yaml \
  --workspace .evosprig/imported-video-studio-state --studio-dir apps/studio/dist
```

In an existing Studio, use **Import project** with this ZIP (use a new project ID if it is already present). Keep the same model/tool profile when starting that Studio. Data collections and running services belong to the deployment; prepare them on the destination as described above.

The ZIP also contains a standalone Python application. Unpack it into a new directory and environment, run `python -m pip install -r requirements.lock`, then `python -m pip install --no-deps .`. Copy your deployment profile and task input there, set the credential variables, and run `python app.py --profile deployment.yaml --input-file input.json --allow-writes`. Resume a paused exported run with `python app.py --resume RUN_ID --path NODE_PATH --response 'RESPONSE_JSON'`.

</details>

The director plans the story; shared character references connect the shots. A vision model checks each first frame. You can replace a frame or shot and keep the rest of the production. Select the director, storyboard or review prompts in **Improve** to evolve them against your own tasks.

| Project | Purpose |
| --- | --- |
| `local-agent.yaml` | Full production workflow |
| `frame-agent.yaml` | Create a replacement first frame |
| `local-shot-agent.yaml` | Generate one shot |
| `compose-agent.yaml` | Assemble clips and subtitles |
| `script-agent.yaml` | Develop stories before rendering |

The included profile uses Kimi K3.1 Pro, FLUX.2-klein-4B and HunyuanVideo-1.5. These shorts contain three five-second silent shots. To connect other providers, edit the [tool bindings](deployment.example.yaml); the [Python builder](build_agent.py) defines the workflows.

## One brief, two workflows

**Laid Off** — a programmer receives an envelope, closes his laptop and leaves with a box.

<table>
<tr>
<td align="center" width="50%"><a href="assets/evosprig.mp4"><img src="assets/evosprig.webp" width="100%" alt="Play VideoClaw (EvoSprig)" /></a><br><b>▶ VideoClaw (EvoSprig)</b></td>
<td align="center" width="50%"><a href="assets/videoclaw.mp4"><img src="assets/videoclaw.webp" width="100%" alt="Play VideoClaw (Original)" /></a><br><b>▶ VideoClaw (Original)</b></td>
</tr>
</table>

[Same brief](brief.json) · [Original VideoClaw workflow](https://github.com/HITsz-TMG/VideoClaw/tree/16c1ce0b553e30eff90ff1274e8a8a63c1d548a3) · [Shared model adapter](../../apps/media-service/videoclaw.py)
