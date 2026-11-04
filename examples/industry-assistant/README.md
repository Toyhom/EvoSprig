# Industry assistant

![The industry agent workflow in EvoSprig Studio](canvas.png)

Develop agents that complete business processes: process a benefits application, handle a financial request or resolve a manufacturing inspection. Give them procedures and business tools, then evaluate the records they actually change.

![Industry environment construction and agent development](../industry-environment-builder/assets/overview.svg)

## A business task, from start to finish

The agent reads the case and operating procedure, searches for the tools it needs, inspects records and performs the required operations. The environment checks the resulting business state against fixed criteria.

| Environment | Agent work |
| --- | --- |
| Finance | Lending, accounts, cards, deposits and investment workflows |
| Government | Benefits applications, eligibility and approval routing |
| Manufacturing | Quality inspections, disposition and follow-up actions |

A task gets its own sandbox, so one run's edits do not change the next run's starting point. People, models and optimizers use the same business criteria.

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

### Prepare the included environment

This folder includes a local training-grant sandbox with eight fictional applications: approvals, income and residency denials, missing documents and conflicting records. It uses the same session and replay interface as an IndustryBench installation.

```bash
export INDUSTRYBENCH_ROOT="$PWD/examples/industry-assistant/starter"
evosprig industry prepare --industry government --limit 8 \
  --out .evosprig/grant-agent
export DEEPSEEK_API_KEY="your-api-key"
```

The command creates `agent.yaml`, editable `prompts/procedure.md`, a task `suite.yaml` and `deployment.yaml`. The model settings are in `.evosprig/grant-agent/deployment.yaml`, under `models.main-model`: `base_url: https://api.deepseek.com`, `model: deepseek-flash`, and `api_key_env: DEEPSEEK_API_KEY`. To use another OpenAI-compatible model, change these three values and export the chosen credential variable. `.env` files are not loaded automatically.

### Run the business cases

```bash
evosprig evaluate .evosprig/grant-agent/agent.yaml \
  --suite .evosprig/grant-agent/suite.yaml \
  --profile .evosprig/grant-agent/deployment.yaml \
  --workspace .evosprig/grant-evaluation
```

Each case starts from fresh application records. The agent reads the procedure, discovers tools, records a decision and reads it back. The evaluator replays those operations against fixed rules and reports the task score. Keep the command's report path to inspect case outputs.

To use your own IndustryBench installation, set `INDUSTRYBENCH_ROOT` to the directory containing `industrybench/session.py`, `registry.py` and `evaluation.py`, and install that distribution's dependencies. Run `industry prepare` into a new output directory, choosing `finance`, `government` or `manufacturing`. At least four distinct cases are needed to form the three evaluation splits.

### Open the canvas and keep developing

Install **Node.js 20+**, then:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
evosprig serve --project .evosprig/grant-agent/agent.yaml \
  --profile .evosprig/grant-agent/deployment.yaml \
  --workspace .evosprig/grant-studio --studio-dir apps/studio/dist
```

Open **http://127.0.0.1:18766**. The project is loaded into the canvas. Edit the procedure and tool budgets, then use **Improve** with the generated suite. Business tools are provided by an evaluation session; use Evaluate/Improve for this application rather than the ordinary Run button.

To continue on another installation, copy the generated project directory and the environment package, set the same credential/root variables, and use `evosprig serve --project PATH/agent.yaml --profile PATH/deployment.yaml` there. The [framework setup](../../README.md#get-started) covers SDK development. The environment stays connected through `evaluation.industry` in the profile.

## Improve the operating instructions

```bash
evosprig improve .evosprig/grant-agent/agent.yaml \
  --suite .evosprig/grant-agent/suite.yaml --profile .evosprig/grant-agent/deployment.yaml \
  --method reflexion --resource procedure --rounds 2 \
  --max-evaluations 100 --timeout 1800
```

Compare the procedure edits and business outcomes, then adopt the version you want. In Studio, load the same profile and task suite in **Improve**.

Need a different business process? Start with the [environment builder](../industry-environment-builder/). For setup, task splits and tool limits, see the [industry guide](../../docs/industry-environments.md).
