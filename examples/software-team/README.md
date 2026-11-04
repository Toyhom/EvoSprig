# Software team

![Workflow in EvoSprig Studio](canvas.png)

Turn a product brief into a working web app. A product manager, designer, developer and reviewer share one workflow; the browser opens the actual HTML and checks its interactions.

**Brief → design → implementation → browser checks → repair → verification → handoff**

<img src="assets/app.png" alt="A generated expense tracker with working add, delete and totals" width="100%" />

## A working expense tracker

The application above supports adding expenses, deleting entries and updating totals. The team turns the brief into HTML, opens it in a browser, checks the requested interactions and feeds failures back into the repair stage.

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
python examples/quickstart.py software-team setup
export DEEPSEEK_API_KEY="your-api-key"
```

The application uses **`deepseek-flash`** at **`https://api.deepseek.com`**. Its settings are in `.evosprig/examples/software-team/deployment.yaml`: change `base_url`, `model` and `api_key_env` under `models` to use another OpenAI-compatible endpoint. When changing providers, also remove or update provider-specific `options`, `token_limit_field` and `send_sampling_parameters` in that connection. Set the environment variable named by `api_key_env` in each terminal that starts or resumes the app. API keys are read from that variable; `.env` files are not loaded automatically.

Setup also creates `.evosprig/examples/software-team/input.json` from the included [sample.json](sample.json). Edit this input for your task. Repeating setup preserves your profile and input.

### Start the tool service

Install **Node.js 20+**, then run this in a second terminal from the checkout:

```bash
npm --prefix apps/toolbox ci
(cd apps/toolbox && npx playwright install --with-deps chromium --only-shell)
npm --prefix apps/toolbox start
```

Leave it running at **http://127.0.0.1:18769**. It opens the generated HTML and checks the requested browser interactions. To use another tool service, change the `tools` endpoints in this application's deployment file.

### Run a task

```bash
python examples/quickstart.py software-team run
```

The output includes the generated HTML, browser check results and artifact URLs. Runs and checkpoints stay in `.evosprig/examples/software-team`. To use a separate input file, append `--input-file /path/to/task.json`.

### Open the canvas and keep developing

Install **Node.js 20+** and build the editor once:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py software-team studio
```

Open **http://127.0.0.1:18766**, select **Live model** and paste `input.json` into Run. Use **History** to inspect steps. Change the port with `--port 18768` if needed.

This loads the application into your Studio workspace. Edit its prompt, skill, model and tool settings on the canvas; use **Debug selection** to try a node or group. The same workflow is defined in [agent.yaml](agent.yaml). For framework installation and SDK development, see [Get started](../../README.md#get-started).

<details>
<summary>Import into another EvoSprig workspace or export an independent application</summary>

```bash
python examples/quickstart.py software-team pack --out .evosprig/software-team.zip
evosprig import .evosprig/software-team.zip --out .evosprig/imported-software-team
evosprig serve --project .evosprig/imported-software-team/agent.yaml \
  --profile .evosprig/examples/software-team/deployment.yaml \
  --workspace .evosprig/imported-software-team-state --studio-dir apps/studio/dist
```

In an existing Studio, use **Import project** with this ZIP (use a new project ID if it is already present). Keep the same model/tool profile when starting that Studio. Data collections and running services belong to the deployment; prepare them on the destination as described above.

The ZIP also contains a standalone Python application. Unpack it into a new directory and environment, run `python -m pip install -r requirements.lock`, then `python -m pip install --no-deps .`. Copy your deployment profile and task input there, set the credential variables, and run `python app.py --profile deployment.yaml --input-file input.json`. Resume a paused exported run with `python app.py --resume RUN_ID --path NODE_PATH --response 'RESPONSE_JSON'`.

</details>

## Make it yours

Edit `sample.json` for your own task and the files under `prompts/` for the roles and instructions. All coordination, tool calls and parallel work use EvoSprig's AgentSpec and runtime. The [catalog builder](../build_catalog.py) shows how to create the same workflow with the Python SDK.

Use the [evolution guide](../../docs/evolution.md) to improve selected prompts and skills on your own tasks.

Application pattern inspired by [MetaGPT’s software company](https://github.com/FoundationAgents/MetaGPT); implemented with EvoSprig's own framework.
