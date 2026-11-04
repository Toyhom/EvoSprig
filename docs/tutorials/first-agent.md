# Your first agent

[English](first-agent.md) · [简体中文](../zh-CN/tutorials/first-agent.md) · [Learning path](README.md)

**Goal:** create a workflow, run it and change its instructions on the canvas. You need Python 3.12+, Git and, for Studio, Node.js 20+.

## 1. Install and create

Run these commands in a terminal:

```bash
git clone --depth 1 https://github.com/Toyhom/EvoSprig.git
cd EvoSprig
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[models,server]'
python docs/tutorials/first_agent.py
```

The last command writes `.evosprig/tutorial/agent.yaml`. Open [first_agent.py](first_agent.py): `default_model("main")` defines the shared model connection. The assistant inherits it; the output binding selects the assistant's text.

## 2. Run the workflow

```bash
evosprig run .evosprig/tutorial/agent.yaml \
  --workspace .evosprig/tutorial-state \
  --input '{"question":"How do I start a reading habit?"}' --mock
```

You should see `status: succeeded` and an `answer` beginning with `Mock:`. This first run checks the workflow without requiring an API account.

For a real response, create `.evosprig/tutorial/deployment.yaml`:

```yaml
models:
  main:
    base_url: https://api.deepseek.com
    model: deepseek-flash
    api_key_env: DEEPSEEK_API_KEY
```

Set `DEEPSEEK_API_KEY` in your terminal, replace the provider settings if needed, then repeat the run with `--profile .evosprig/tutorial/deployment.yaml` and without `--mock`. [Model connection fields](../model-connections.md).

## 3. Open the canvas

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --project .evosprig/tutorial/agent.yaml \
  --workspace .evosprig/tutorial-studio --profile .evosprig/tutorial/deployment.yaml \
  --studio-dir apps/studio/dist --port 18766
```

Open `http://127.0.0.1:18766`. Select the assistant, change **Instructions** to “Answer in one sentence, then give one small action to try today”, and save. Enter the same question, choose **Live models**, and run again. Compare the two answers in **History**.

## 4. Try one change

Change only the instruction. Keep the question and model fixed so you can see what the change does. Open **Python** to view the code for the saved application.

If the model fails to connect, check the base URL, model ID and environment variable in the same terminal that starts Studio. If port 18766 is busy, choose another with `--port`.

**Next:** [build a comic application on the canvas](comic-studio.md).
