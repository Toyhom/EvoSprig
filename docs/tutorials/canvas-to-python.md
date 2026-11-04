# Move from canvas to Python

[English](canvas-to-python.md) · [简体中文](../zh-CN/tutorials/canvas-to-python.md) · [Learning path](README.md)

**Goal:** keep developing the comic workflow in an editor and run its exported application independently.

## 1. Save and inspect

In the comic project, save your changes and open **Python**. Find the model definitions, resource declarations, node inputs and output bindings. Follow `panels` into its map and loop bodies. The generated Builder code describes the same saved AgentSpec.

## 2. Export a runnable project

Choose **Python** in the export selector and download the ZIP. Unpack it in a new directory. It contains `agent.yaml`, resources, runtime code, `app.py` and dependencies.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python app.py --profile deployment.yaml --input-file input.json --allow-writes
```

Copy your deployment profile and story input into this directory, set its API-key environment variables and keep the referenced image service running. Exporting an agent does not copy model weights or credentials.

## 3. Use one default and one override

When authoring with the SDK:

```python
DEFAULT_MODEL = "writing-api"
builder.default_model(DEFAULT_MODEL, ["text", "structured_output"])
builder.model("vision", "local-vision", ["text", "structured_output", "vision"])
# A writer node can omit model= and use main.
# A reviewer sets model="vision" explicitly.
```

`main` is the shared alias. Changing its deployment binding updates all nodes using it, including nested subflows. An explicit `vision` alias keeps its own connection. [Configure GPU placement and preload](../local-models.md).

## 4. Return to Studio

Import the exported ZIP through **Import project**, choose a project ID, and reconnect the deployment profile. Save a new ZIP after changes. Keep the previous working version so you can compare behavior.

For source development inside the repository, edit [build_agent.py](../../examples/comic-studio/build_agent.py), run it to regenerate `agent.yaml`, then open that spec in a new Studio project. [Import and export contracts](../deployment.md).

**Next:** [evaluate and improve an agent](improve-an-agent.md).
