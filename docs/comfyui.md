# ComfyUI tools

Import a ComfyUI graph into Studio, edit its parameters and export it back. Each computation becomes a tool node. Models, adapters, conditioning, sampling and output nodes keep their individual connections.

## Open a workflow

In Studio, choose **ComfyUI · Import workflow**, select the workflow JSON and enter the ComfyUI server address. **Check nodes and parameters** reads the installed node definitions. Choose **Open on canvas** to create the project.

Select **Add a render node** to submit the assembled graph when it runs. Leave it unchecked to inspect the prepared graph before generating media.

The same import is available from the CLI:

```bash
evosprig comfy import workflow.json --server http://127.0.0.1:8188 \
  --id film-render --out film-render
evosprig serve --project film-render/agent.yaml \
  --profile film-render/deployment.yaml --studio-dir apps/studio/dist
```

An offline import accepts a saved response from `/object_info`:

```bash
evosprig comfy import workflow.json --schema object-info.json \
  --prepare-only --out film-render
```

## Edit and export

Select a tool node to change its inputs. Connected inputs follow their source node. Use **Debug selection** to check one node or a group with saved upstream values. Preparation runs produce a JSON graph; the render node submits it to ComfyUI and returns the saved outputs.

The Studio ComfyUI export retains layout, notes, bypass states and extension metadata. Its API form contains the executable graph. CLI edits use a small patch file:

```json
{
  "12": {"inputs": {"steps": 14}},
  "8": {"enabled": false}
}
```

```bash
evosprig comfy export workflow.json --schema object-info.json \
  --patch changes.json --out edited-workflow.json
```

An API graph can also become an editable ComfyUI canvas:

```bash
evosprig comfy export prompt.json --schema object-info.json \
  --format ui --out editable-workflow.json
```

Connections, parameter widgets and fixed seeds are restored from the installed node definitions. Render failures appear in the run events with the affected node and service message; use **Debug selection** to check the corrected inputs.

## Let an agent choose parameters

Use a `comfy_recipe` binding to expose selected controls from a saved graph. Omitted controls retain the graph's defaults. Each call starts from that saved graph, so one shot's settings do not leak into the next.

For a value controlled by an upstream slider or primitive, expose that source node's value. Recipe validation checks connected inputs before rendering.

```python
from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool

config = ComfyRecipeConfig(
    name="film.recipe",
    workflow=workflow_json,
    object_info=installed_node_schemas,
    outputs=["save_video"],
    parameters={
        "steps": {"node_id": "sampler", "input_name": "steps",
                  "schema": {"minimum": 12, "maximum": 16}},
        "action": {"node_id": "action_lora", "kind": "enabled"},
    },
    reference_slots=[{"node_id": "character_image"}],
)
tool = comfy_recipe_tool(config)
prepared = await tool.invoke({
    "controls": {"steps": 14, "action": True},
    "reference_images": ["generated-character.png"],
})
```

Reference images must already be in the ComfyUI input directory. The [media service](../apps/media-service/) can stage generated assets there. Unused reference slots are disconnected. Use a separate `comfy_job` binding to render `prepared["prompt"]`; its submit/poll/cancel lifecycle uses the regular runtime journal.

For audiovisual workflows, declare `audio_slots` and `video_slots` with each loader's `node_id` and `input_name`. Calls accept `reference_audio` and `reference_videos` alongside `reference_images`. Use `also_nodes` on an `enabled` parameter to switch a whole adapter chain together. An explicit switch for one node overrides a group switch, so the agent can select a preset and adjust individual adapters.

Expose the same configuration under `kind: comfy_recipe_info` with a separate tool name to let an agent read its controls and saved defaults. This read-only tool returns `controls` (JSON Schema), `defaults` and `reference_limits`. The [episode team](../examples/episode-studio/) uses these values to choose LoRA strengths, sampling and upscaling settings. Its output validator checks the proposed controls before submitting a render.

For a dedicated ComfyUI process, set `dedicated: true` to allow interruption and model unloading. Shared instances support cancellation of queued jobs. A lost submission response is reconciled with the queue/history before another render is considered.
