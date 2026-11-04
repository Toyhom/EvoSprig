# Office deliverables

![Office deliverables in EvoSprig](assets/canvas.png)

[English](README.md) · [简体中文](README.zh-CN.md)

**Turn a table into an editable workbook, a management brief and a slide deck.**

Application inspiration: [LiveDoc](https://agent2048.com/zh/projects/9ygfsksfp7qu).

## A finished result

![Quarterly report](assets/result.png)

A quarterly sales table becomes a brief with **134,000 revenue**, **34,300 profit**, **25.60% margin** and **670 orders**. The workbook formulas, document and slides share these numbers.

## How it works

Calculate the ledger → write a focused brief → build XLSX, DOCX and PPTX from the same numbers. Excel includes formulas and cached results. The preview opens directly in a browser.

## Run it

Use Python 3.12+ and Git. In a new terminal:

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[models,server,artifacts]"
export DEEPSEEK_API_KEY="your-api-key"
python examples/quickstart.py office-deliverables setup
```

Set the API URL, model ID and key variable in `.evosprig/examples/office-deliverables/deployment.yaml`: `models.main.base_url`, `model`, and `api_key_env`. The default uses DeepSeek. OpenAI-compatible APIs and local models also work. Set the key in each new terminal; `.env` files are not loaded automatically.

Or choose a different provider during the first setup:

```bash
export MODEL_API_KEY="your-api-key"
python examples/quickstart.py office-deliverables setup \
  --workspace .evosprig/my-office-deliverables \
  --base-url https://your-provider.example/v1 --model your-model-id --key-env MODEL_API_KEY
```

Edit `.evosprig/examples/office-deliverables/input.json`, then run:

```bash
python examples/quickstart.py office-deliverables run --allow-writes
```

If setup used a custom workspace, pass the same `--workspace` to run, studio and pack. See [sample.json](sample.json) and [agent.yaml](agent.yaml) for the input fields.

The output JSON includes `directory`, containing the generated files under the workspace’s `artifacts` folder. Keep the same workspace to retain run history.

## Continue in the canvas

With Node.js 20+:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py office-deliverables studio --port 18766
```

Open `http://127.0.0.1:18766`, choose Live model and allow tool writes. Edit nodes, prompts and skills, or debug a selected step.

Export the application and import it into another EvoSprig workspace:

```bash
python examples/quickstart.py office-deliverables pack --out office-deliverables.zip
```

Use **Import project** in Studio. To run the ZIP independently, extract it, install its `requirements.lock` and bundled runtime, then use `python app.py --profile deployment.yaml --input-file input.json --allow-writes`. Supply your deployment profile and input data. See the [developer guide](../../docs/build-applications.md) for framework setup and extension.

```bash
python examples/office-deliverables/from_csv.py sales.csv --goal "Review margin and orders" --out task.json
python examples/quickstart.py office-deliverables run --input-file task.json --allow-writes
```

CSV columns: `period,revenue,cost,orders`.
