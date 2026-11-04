# Career coach

![Workflow in EvoSprig Studio](canvas.png)

Turn a resume and a job description into a tailored application and an interview practice session. Role-fit analysis feeds two parallel writers; the candidate answers a question before receiving feedback.

## From experience to application materials

![Tailored resume summary and interview coaching from the selected version](assets/result.png)

The coach prepares a PHP/Laravel summary, specific resume bullets and a practice plan. It asks about missing qualifications before adding them to the application. This output uses a public job description from [lang-uk’s recruitment dataset](https://huggingface.co/datasets/lang-uk/recruitment-dataset-job-descriptions-english) (MIT) and a fictional applicant profile, with DeepSeek Flash.

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
python examples/quickstart.py career-coach setup
export DEEPSEEK_API_KEY="your-api-key"
```

The application uses **`deepseek-flash`** at **`https://api.deepseek.com`**. Its settings are in `.evosprig/examples/career-coach/deployment.yaml`: change `base_url`, `model` and `api_key_env` under `models` to use another OpenAI-compatible endpoint. When changing providers, also remove or update provider-specific `options`, `token_limit_field` and `send_sampling_parameters` in that connection. Set the environment variable named by `api_key_env` in each terminal that starts or resumes the app. API keys are read from that variable; `.env` files are not loaded automatically.

Setup also creates `.evosprig/examples/career-coach/input.json` from the included [sample.json](sample.json). Edit this input for your task. Repeating setup preserves your profile and input.

### Run a task

```bash
python examples/quickstart.py career-coach run
```

The final output contains application material and feedback on your interview answer. Runs and checkpoints stay in `.evosprig/examples/career-coach`. To use a separate input file, append `--input-file /path/to/task.json`.

A `waiting_input` result pauses at `graph/practice`. Read the interview question and supply your answer. Copy the `run_id` from the result and continue:

```bash
evosprig inspect RUN_ID --workspace .evosprig/examples/career-coach
evosprig resume RUN_ID --workspace .evosprig/examples/career-coach \
  --path graph/practice --response '{"answer": "I automated a weekly report with SQL and Python, reducing preparation from three hours to twenty minutes."}'
```

### Open the canvas and keep developing

Install **Node.js 20+** and build the editor once:

```bash
npm --prefix apps/studio ci
npm --prefix apps/studio run build
python examples/quickstart.py career-coach studio
```

Open **http://127.0.0.1:18766**, select **Live model** and paste `input.json` into Run. Use **History** to inspect steps and respond to review/input requests. Change the port with `--port 18768` if needed.

This loads the application into your Studio workspace. Edit its prompt, skill, model and tool settings on the canvas; use **Debug selection** to try a node or group. The same workflow is defined in [agent.yaml](agent.yaml). For framework installation and SDK development, see [Get started](../../README.md#get-started).

<details>
<summary>Import into another EvoSprig workspace or export an independent application</summary>

```bash
python examples/quickstart.py career-coach pack --out .evosprig/career-coach.zip
evosprig import .evosprig/career-coach.zip --out .evosprig/imported-career-coach
evosprig serve --project .evosprig/imported-career-coach/agent.yaml \
  --profile .evosprig/examples/career-coach/deployment.yaml \
  --workspace .evosprig/imported-career-coach-state --studio-dir apps/studio/dist
```

In an existing Studio, use **Import project** with this ZIP (use a new project ID if it is already present). Keep the same model/tool profile when starting that Studio. Data collections and running services belong to the deployment; prepare them on the destination as described above.

The ZIP also contains a standalone Python application. Unpack it into a new directory and environment, run `python -m pip install -r requirements.lock`, then `python -m pip install --no-deps .`. Copy your deployment profile and task input there, set the credential variables, and run `python app.py --profile deployment.yaml --input-file input.json`. Resume a paused exported run with `python app.py --resume RUN_ID --path NODE_PATH --response 'RESPONSE_JSON'`.

</details>

## Make it yours

Change the role and resume in `sample.json`. Edit `factual_writing` to set your resume conventions and `interview_coaching` to change the practice method. The factual-writing skill is shared by the reviewer, resume writer and final coach.

For unattended improvement, import an [evaluation suite](../../docs/evaluation.md#bring-your-own-task-suite) with an interview answer in each task's `responses`, such as `{"graph/practice": {"answer": "I automated the weekly report with SQL and Python."}}`. Then select prompt or skill resources and an algorithm in **Improve**. EvoSprig runs the same workflow with each candidate. [Agent configuration](../../docs/agent-resources.md) describes resource selection and model parameters.

Built with EvoSprig's [Python SDK](../build_work_apps.py). Application patterns draw on [Coze community resume workflows](https://github.com/AICoderTudou/coze-workflows/tree/main/coze), with application review and interview practice added here.
