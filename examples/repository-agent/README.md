# Super-agent (EvoSprig)

![Repository team on the EvoSprig canvas](assets/canvas.png)

A repository maintenance team based on [DeepSeek's Super-agent prototype](https://github.com/deepseek-ai/dsh-superagent-prototype): read a task, inspect the code, make a patch, run tests and return it for review.

The coordinator plans the change. An engineer edits an independent Git worktree, and a reviewer checks the patch against the request and actual test output. Failed checks return to the engineer for another pass. The final patch opens in a human review step.

## Fix an invoice importer

The team replaced a comma-splitting parser with CSV parsing, preserving Decimal arithmetic and the existing API. The returned patch handles quoted names, BOM and whitespace, optional VAT, duplicate IDs, invalid amounts and rounding.

```text
Input:   I-1,"Studio, Ltd",10.00,0.20
Result:  customer = "Studio, Ltd" · total = Decimal("12.00")

8 checks passed · 1 file changed · ready for review
```

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
python examples/quickstart.py repository-agent setup
export DEEPSEEK_API_KEY="your-api-key"
```

The application uses **`deepseek-flash`** at **`https://api.deepseek.com`**. Its settings are in `.evosprig/examples/repository-agent/deployment.yaml`: change `base_url`, `model` and `api_key_env` under `models` to use another OpenAI-compatible endpoint. When changing providers, also remove or update provider-specific `options`, `token_limit_field` and `send_sampling_parameters` in that connection. Set the environment variable named by `api_key_env` in each terminal that starts or resumes the app. API keys are read from that variable; `.env` files are not loaded automatically.

Setup also creates `.evosprig/examples/repository-agent/input.json` from the included [sample.json](sample.json). Edit this input for your task. Repeating setup preserves your profile and input.

### Choose a repository and its checks

Try the included invoice-parser task first:

```bash
python examples/repository-agent/create_sample.py
export AGENT_REPOSITORY="$PWD/.evosprig/invoice-repository"
```

This creates a committed Git repository with a CSV bug and four `unittest` checks. The default binding permits edits under `src/` and runs `python -m unittest discover -s tests -v`. The team works in a separate Git worktree; the result includes its patch and check output.

For your own project, set `AGENT_REPOSITORY` to its absolute checkout path. It needs a committed `HEAD`; commit the changes the team should see. Install that project's test dependencies in the worker environment, or use the absolute path to its Python interpreter. Configure the allowed paths and named check:

```bash
export AGENT_REPOSITORY="/absolute/path/to/your/repository"
python examples/repository-agent/configure.py \
  --model-url https://api.deepseek.com --model deepseek-flash \
  --editable src/ --out .evosprig/examples/repository-agent/deployment.yaml \
  -- python -m pytest -q
export MODEL_API_KEY="your-api-key"
```

This custom profile uses `MODEL_API_KEY`. Repeat `--editable` for each allowed directory or file. Replace `input.json` with your request and `check: "unit"`; `unit` refers to the configured command. Checks run in the worktree, so install dependencies independently of that checkout. The approval step returns your decision; applying or merging the patch is a separate action.

### Run a task

```bash
python examples/quickstart.py repository-agent run --allow-writes
```

Read the result in the command’s final JSON output. Runs and checkpoints stay in `.evosprig/examples/repository-agent`. To use a separate input file, append `--input-file /path/to/task.json`.

A `waiting_input` result pauses at `graph/approval`. Inspect the patch and actual test output, then approve or reject the proposal. Copy the `run_id` from the result and continue:

```bash
evosprig inspect RUN_ID --workspace .evosprig/examples/repository-agent
evosprig resume RUN_ID --workspace .evosprig/examples/repository-agent \
  --path graph/approval --response '{"decision": "approve", "comment": "Reviewed the patch and check output."}'
```

### Open the canvas and keep developing

Install **Node.js 20+** and build the editor once:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py repository-agent studio
```

Open **http://127.0.0.1:18766**, select **Live model** and paste `input.json` into Run. Enable **Allow writes** for this workflow. Use **History** to inspect steps and respond to review/input requests. Change the port with `--port 18768` if needed.

This loads the application into your Studio workspace. Edit its prompt, skill, model and tool settings on the canvas; use **Debug selection** to try a node or group. The same workflow is defined in [agent.yaml](agent.yaml). For framework installation and SDK development, see [Get started](../../README.md#get-started).

<details>
<summary>Import into another EvoSprig workspace or export an independent application</summary>

```bash
python examples/quickstart.py repository-agent pack --out .evosprig/repository-agent.zip
evosprig import .evosprig/repository-agent.zip --out .evosprig/imported-repository-agent
evosprig serve --project .evosprig/imported-repository-agent/agent.yaml \
  --profile .evosprig/examples/repository-agent/deployment.yaml \
  --workspace .evosprig/imported-repository-agent-state --studio-dir apps/studio/dist
```

In an existing Studio, use **Import project** with this ZIP (use a new project ID if it is already present). Keep the same model/tool profile when starting that Studio. Data collections and running services belong to the deployment; prepare them on the destination as described above.

The ZIP also contains a standalone Python application. Unpack it into a new directory and environment, run `python -m pip install -r requirements.lock`, then `python -m pip install --no-deps .`. Copy your deployment profile and task input there, set the credential variables, and run `python app.py --profile deployment.yaml --input-file input.json --allow-writes`. Resume a paused exported run with `python app.py --resume RUN_ID --path NODE_PATH --response 'RESPONSE_JSON'`.

</details>

## Adapt the team

Edit `prompts/` and `skills/repository.md` for your coding conventions. [Repository bindings](../../docs/repository-tools.md) define the editable files, test commands and execution limits. Use a container worker for untrusted repositories.

The [search space](search-space.yaml) exposes planning, implementation and review instructions, along with tool and revision budgets. Evaluate candidates on your own repository tasks and executable checks with **Improve**.
