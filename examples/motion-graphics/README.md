# Motion graphics

![Workflow in EvoSprig Studio](canvas.png)

Render an original 18-second animation with a storyboard, a human checkpoint and a separate CPU render service. This example demonstrates external-job execution with an actual MP4 artifact.

![Three rendered shots](assets/contact-sheet.png)

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
python examples/quickstart.py motion-graphics setup
export DEEPSEEK_API_KEY="your-api-key"
```

The application uses **`deepseek-flash`** at **`https://api.deepseek.com`**. Its settings are in `.evosprig/examples/motion-graphics/deployment.yaml`: change `base_url`, `model` and `api_key_env` under `models` to use another OpenAI-compatible endpoint. When changing providers, also remove or update provider-specific `options`, `token_limit_field` and `send_sampling_parameters` in that connection. Set the environment variable named by `api_key_env` in each terminal that starts or resumes the app. API keys are read from that variable; `.env` files are not loaded automatically.

Setup also creates `.evosprig/examples/motion-graphics/input.json` from the included [sample.json](sample.json). Edit this input for your task. Repeating setup preserves your profile and input.

### Start the CPU renderer

In a second terminal, from this checkout:

```bash
source .venv/bin/activate
python -m pip install '.[media]'
export EVOSPRIG_RENDER_TOKEN="local-render-token"
python examples/motion-graphics/renderer_service.py \
  --state .evosprig/renderer --artifacts .evosprig/film-artifacts
```

Set the same `EVOSPRIG_RENDER_TOKEN` in the agent terminal. The renderer listens on **http://127.0.0.1:18880**. Pillow draws the frames; the packaged FFmpeg encodes the MP4. Change both `--port` and the profile's renderer endpoint if this port is occupied.

### Run a task

```bash
python examples/quickstart.py motion-graphics run --allow-writes
```

The output identifies the 18-second MP4 in `.evosprig/film-artifacts`. Runs and checkpoints stay in `.evosprig/examples/motion-graphics`. To use a separate input file, append `--input-file /path/to/task.json`.

The workflow pauses at `graph/review`. In Studio’s **History**, copy the proposed storyboard into the response form, edit it if needed, then submit it. The renderer runs after this review.

### Open the canvas and keep developing

Install **Node.js 20+** and build the editor once:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py motion-graphics studio
```

Open **http://127.0.0.1:18766**, select **Live model** and paste `input.json` into Run. Enable **Allow writes** for this workflow. Use **History** to inspect steps and respond to review/input requests. Change the port with `--port 18768` if needed.

This loads the application into your Studio workspace. Edit its prompt, skill, model and tool settings on the canvas; use **Debug selection** to try a node or group. The same workflow is defined in [agent.yaml](agent.yaml). For framework installation and SDK development, see [Get started](../../README.md#get-started).

<details>
<summary>Import into another EvoSprig workspace or export an independent application</summary>

```bash
python examples/quickstart.py motion-graphics pack --out .evosprig/motion-graphics.zip
evosprig import .evosprig/motion-graphics.zip --out .evosprig/imported-motion-graphics
evosprig serve --project .evosprig/imported-motion-graphics/agent.yaml \
  --profile .evosprig/examples/motion-graphics/deployment.yaml \
  --workspace .evosprig/imported-motion-graphics-state --studio-dir apps/studio/dist
```

In an existing Studio, use **Import project** with this ZIP (use a new project ID if it is already present). Keep the same model/tool profile when starting that Studio. Data collections and running services belong to the deployment; prepare them on the destination as described above.

The ZIP also contains a standalone Python application. Unpack it into a new directory and environment, run `python -m pip install -r requirements.lock`, then `python -m pip install --no-deps .`. Copy your deployment profile and task input there, set the credential variables, and run `python app.py --profile deployment.yaml --input-file input.json --allow-writes`. Resume a paused exported run with `python app.py --resume RUN_ID --path NODE_PATH --response 'RESPONSE_JSON'`.

</details>
