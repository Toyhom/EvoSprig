# Book studio

![Workflow in EvoSprig Studio](canvas.png)

Turn an idea into a short guide. Plan a shared outline, write chapters in parallel and review consistency across the finished manuscript.

**Brief → outline → parallel chapter writers → editorial handoff**

<img src="assets/comparison.png" alt="Original and evolved chapters for the same community-event brief" width="100%" />

## What evolution changed

APE revised the outline and chapter prompts to preserve shared constraints and separate chapter responsibilities. In the original community-event guide, different chapters assign different amounts to the same budget items. The selected chapter follows the shared allocation and keeps coordination free.

The mean judge score was **0.740 → 0.895** across two held-out writing tasks, with DeepSeek Flash generating and judging. This folder contains the selected prompts.

### Improve your own writing team

Open **Improve** in Studio, add your writing briefs as task inputs, select `outline` and `chapter`, and choose APE. EvoSprig proposes edits, runs the workflow and compares the versions. You can also select a reusable skill attached to a writer, such as a style guide or editing checklist. Review the changes and enable the version you want to use.

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
python examples/quickstart.py book-studio setup
export DEEPSEEK_API_KEY="your-api-key"
```

The application uses **`deepseek-flash`** at **`https://api.deepseek.com`**. Its settings are in `.evosprig/examples/book-studio/deployment.yaml`: change `base_url`, `model` and `api_key_env` under `models` to use another OpenAI-compatible endpoint. When changing providers, also remove or update provider-specific `options`, `token_limit_field` and `send_sampling_parameters` in that connection. Set the environment variable named by `api_key_env` in each terminal that starts or resumes the app. API keys are read from that variable; `.env` files are not loaded automatically.

Setup also creates `.evosprig/examples/book-studio/input.json` from the included [sample.json](sample.json). Edit this input for your task. Repeating setup preserves your profile and input.

### Run a task

```bash
python examples/quickstart.py book-studio run
```

The final JSON contains the outline, chapters and editorial handoff. Runs and checkpoints stay in `.evosprig/examples/book-studio`. To use a separate input file, append `--input-file /path/to/task.json`.

### Open the canvas and keep developing

Install **Node.js 20+** and build the editor once:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py book-studio studio
```

Open **http://127.0.0.1:18766**, select **Live model** and paste `input.json` into Run. Use **History** to inspect steps. Change the port with `--port 18768` if needed.

This loads the application into your Studio workspace. Edit its prompt, skill, model and tool settings on the canvas; use **Debug selection** to try a node or group. The same workflow is defined in [agent.yaml](agent.yaml). For framework installation and SDK development, see [Get started](../../README.md#get-started).

<details>
<summary>Import into another EvoSprig workspace or export an independent application</summary>

```bash
python examples/quickstart.py book-studio pack --out .evosprig/book-studio.zip
evosprig import .evosprig/book-studio.zip --out .evosprig/imported-book-studio
evosprig serve --project .evosprig/imported-book-studio/agent.yaml \
  --profile .evosprig/examples/book-studio/deployment.yaml \
  --workspace .evosprig/imported-book-studio-state --studio-dir apps/studio/dist
```

In an existing Studio, use **Import project** with this ZIP (use a new project ID if it is already present). Keep the same model/tool profile when starting that Studio. Data collections and running services belong to the deployment; prepare them on the destination as described above.

The ZIP also contains a standalone Python application. Unpack it into a new directory and environment, run `python -m pip install -r requirements.lock`, then `python -m pip install --no-deps .`. Copy your deployment profile and task input there, set the credential variables, and run `python app.py --profile deployment.yaml --input-file input.json`. Resume a paused exported run with `python app.py --resume RUN_ID --path NODE_PATH --response 'RESPONSE_JSON'`.

</details>

## Make it yours

Edit `sample.json` for your own task and the files under `prompts/` for the roles and instructions. All coordination, tool calls and parallel work use EvoSprig's AgentSpec and runtime. The [catalog builder](../build_catalog.py) shows how to create the same workflow with the Python SDK.

Use the [evolution guide](../../docs/evolution.md) to improve selected prompts and skills on your own tasks.

Application pattern inspired by [CrewAI’s book-writing workflow](https://github.com/crewAIInc/crewAI-examples); implemented with EvoSprig's own framework.
