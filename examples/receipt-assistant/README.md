# Receipt assistant

![Workflow in EvoSprig Studio](canvas.png)

Turn a receipt photo into structured expenses. Read the image, extract the printed amounts, check the arithmetic and review it against your expense policy.

**Image → OCR → structured receipt → calculation and policy review**

## From receipt to expense review

![Selected application result](assets/result.png)

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
python examples/quickstart.py receipt-assistant setup
export DEEPSEEK_API_KEY="your-api-key"
```

The application uses **`deepseek-flash`** at **`https://api.deepseek.com`**. Its settings are in `.evosprig/examples/receipt-assistant/deployment.yaml`: change `base_url`, `model` and `api_key_env` under `models` to use another OpenAI-compatible endpoint. When changing providers, also remove or update provider-specific `options`, `token_limit_field` and `send_sampling_parameters` in that connection. Set the environment variable named by `api_key_env` in each terminal that starts or resumes the app. API keys are read from that variable; `.env` files are not loaded automatically.

Setup also creates `.evosprig/examples/receipt-assistant/input.json` from the included [sample.json](sample.json). Edit this input for your task. Repeating setup preserves your profile and input.

### Start the tool service

Install **Node.js 20+**, then run this in a second terminal from the checkout:

```bash
npm --prefix apps/toolbox ci
(cd apps/toolbox && npx playwright install --with-deps chromium --only-shell)
npm --prefix apps/toolbox start
```

Leave it running at **http://127.0.0.1:18769**. It provides English receipt OCR and Python arithmetic checks. The supplied input already contains the sample receipt image. To use another tool service, change the `tools` endpoints in this application's deployment file.

### Run a task

```bash
python examples/quickstart.py receipt-assistant run
```

The output contains the extracted receipt, arithmetic checks and policy review. Runs and checkpoints stay in `.evosprig/examples/receipt-assistant`. To use a separate input file, append `--input-file /path/to/task.json`.

### Open the canvas and keep developing

Install **Node.js 20+** and build the editor once:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py receipt-assistant studio
```

Open **http://127.0.0.1:18766**, select **Live model** and paste `input.json` into Run. Use **History** to inspect steps. Change the port with `--port 18768` if needed.

This loads the application into your Studio workspace. Edit its prompt, skill, model and tool settings on the canvas; use **Debug selection** to try a node or group. The same workflow is defined in [agent.yaml](agent.yaml). For framework installation and SDK development, see [Get started](../../README.md#get-started).

<details>
<summary>Import into another EvoSprig workspace or export an independent application</summary>

```bash
python examples/quickstart.py receipt-assistant pack --out .evosprig/receipt-assistant.zip
evosprig import .evosprig/receipt-assistant.zip --out .evosprig/imported-receipt-assistant
evosprig serve --project .evosprig/imported-receipt-assistant/agent.yaml \
  --profile .evosprig/examples/receipt-assistant/deployment.yaml \
  --workspace .evosprig/imported-receipt-assistant-state --studio-dir apps/studio/dist
```

In an existing Studio, use **Import project** with this ZIP (use a new project ID if it is already present). Keep the same model/tool profile when starting that Studio. Data collections and running services belong to the deployment; prepare them on the destination as described above.

The ZIP also contains a standalone Python application. Unpack it into a new directory and environment, run `python -m pip install -r requirements.lock`, then `python -m pip install --no-deps .`. Copy your deployment profile and task input there, set the credential variables, and run `python app.py --profile deployment.yaml --input-file input.json`. Resume a paused exported run with `python app.py --resume RUN_ID --path NODE_PATH --response 'RESPONSE_JSON'`.

</details>

## Make it yours

Edit `sample.json` for your own task and the files under `prompts/` for the roles and instructions. All coordination, tool calls and parallel work use EvoSprig's AgentSpec and runtime. The [catalog builder](../build_catalog.py) shows how to create the same workflow with the Python SDK.

Use the [evolution guide](../../docs/evolution.md) to improve selected prompts and skills on your own tasks.

Application pattern inspired by [MetaGPT’s receipt assistant](https://github.com/FoundationAgents/MetaGPT); implemented with EvoSprig's own framework.

<img src="receipt.png" alt="Example receipt" width="280" />

For another image, base64-encode its bytes into the `image_base64` input. The workflow sends the image to OCR and only the resulting text to the extraction model.
