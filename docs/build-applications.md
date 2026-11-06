# Build an agent application

[English](build-applications.md) · [简体中文](zh-CN/build-applications.md) · [Documentation](README.md)

An EvoSprig application combines a graph, editable resources and deployment bindings. The same AgentSpec opens in Studio and runs through the Python runtime.

## Start from a working application

Choose [Episode Studio](../examples/episode-studio/) for animated stories, [Super-agent](../examples/repository-agent/) for repository work, [CoworkOS](../examples/cowork/) for a collaborative team, or a smaller [example](../examples/). Install EvoSprig using the [quickstart](quickstart.md).

```bash
evosprig serve --project examples/cowork/agent.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/cowork
```

Open `http://127.0.0.1:18766`. Configure your model connection, edit the request and run the application.

## Design on the canvas

1. Add a **model** node for one generation or an **agent** node for a model that can choose tools.
2. Attach a prompt and reusable skills in the node inspector. Set the output schema and model limits.
3. Add **tool** nodes for required operations such as OCR, saving a file or assembling video. Give agents a tool allowlist for operations they choose dynamically.
4. Connect data through input references. Use **parallel** for named branches and **map** for a task list created at runtime.
5. Add **human** nodes where a person reviews or edits an output. Use loops for bounded revision cycles.
6. Group related nodes; open nested subflows to edit their execution logic. Save and run.

**History** shows the active step and waiting requests. Respond to an approval to continue the same run. **Memory** manages agent facts and working context; **Knowledge** manages business documents and retrieval. See the [Studio guide](studio.md) for controls and keyboard shortcuts.

Select one or more nodes and choose **Debug selection** to test that section. Fill the generated input form or reuse outputs from the last run. Inside a map or retry loop, select the saved item or take to restore its inputs and prior state. Collapsed groups can be selected together. The debug run uses the same model, tools and permissions as the application.

For image and video pipelines, [import a ComfyUI workflow](comfyui.md) to turn its computations into editable tool nodes.

## Design in Python

Save this as `build_agent.py` beside `prompts/draft.md` and `skills/style.md`:

```python
from evosprig.sdk import Builder
from evosprig.core.spec import save_spec

text = {"type": "string"}
output = {"type": "object", "properties": {"text": text}, "required": ["text"]}
app = (
    Builder("writing-assistant",
            {"type": "object", "properties": {"brief": text}, "required": ["brief"]},
            output)
    .model("writer", "main")
    .resource("draft", "prompts/draft.md")
    .skill("style", "skills/style.md")
    .node("write", "model", model="writer",
          instructions={"resource": "draft"}, skills=["style"],
          inputs={"brief": {"ref": "input.brief"}},
          output_schema=output, max_output_tokens=2048)
    .output(text={"ref": "nodes.write.output.text"})
    .execution(max_total_tokens=12000)
    .build_spec()
)
save_spec(app, "agent.yaml")
```

Run `python build_agent.py`, then:

```bash
evosprig run agent.yaml --input '{"brief":"Draft a customer invitation"}'
evosprig serve --project agent.yaml --studio-dir apps/studio/dist
```

For embedded execution, compile and run the same specification:

```python
from pathlib import Path
from evosprig.config import make_models, make_tools
from evosprig.core.journal import Scope
from evosprig.core.runtime import Runtime
from evosprig.core.version import compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal

workspace = Path(".evosprig")
version = compile_agent(app, Path("."))
runtime = Runtime(
    make_models(app), make_tools(workspace, Scope(app.id)),
    journal=SQLiteJournal(workspace / "runs.sqlite"),
)
result = await runtime.run(version, {"brief": "Draft a customer invitation"})
```

## Connect tools and state

Declare tool aliases in the application and configure HTTP, MCP or database bindings in a [deployment profile](tools.md). Built-in [memory](memory.md) and [shared document tools](shared-workspaces.md) use the application's workspace and identity. Long jobs implement `ExternalTool`: submit, poll and cancel. The runtime checkpoints their receipts and resumes after completion.

Use `allow_side_effects=True` in the graph and `--allow-writes` for a run that saves documents or invokes write tools.

For rules that depend on the request, attach a bounded Python code resource with `output_validator="check_plan"` to a model or agent node (spec 0.3). Its `run(inputs)` receives `inputs["input"]` and `inputs["output"]`, and returns `{"valid": bool, "feedback": str}`. Image input fields are omitted. For example, validate that a generated itinerary uses requested cities, or that shot references name declared characters. With `output_errors="feedback"`, the model receives the failed rule and repairs its answer within `max_output_retries`. Studio exposes this under **Application validation**.

## Add self-evolution

1. Put representative requests in JSONL, one input object per line.
2. In **Improve**, import those inputs and define your evaluation rubric, or import an [EvalSuite](evaluation.md) with references, tool checks and environment outcomes.
3. Select attached prompt/skill resources and a method, then set the budget.
4. Start the study. Inspect the resource diff and application outputs.
5. Enable the selected version in **Versions**.

Search can cover prompts, skills, code resources, harness settings, model routing, memory parameters and workflow structure. Define the permitted search space and evaluation tasks in advance. [Evolution components](evolution-components.md) explains the component map.

## Ship

Use [export](deployment.md) for standalone Python, an HTTP application or a container build project. Bind deployment credentials through environment variables and load the application's data into its workspace.
