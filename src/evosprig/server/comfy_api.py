"""ComfyUI import and roundtrip export for Studio."""

from copy import deepcopy

from fastapi import HTTPException
from pydantic import Field

from evosprig.core.spec import AgentSpec, Contract
from evosprig.core.version import SECRET, compile_snapshot
from evosprig.integrations.comfyui import ComfyWorkflow
from evosprig.plugins.comfy_tools import import_comfy_spec

from .auth import current_principal


class ImportBody(Contract):
    workflow: dict
    object_info: dict = Field(default_factory=dict)
    project_id: str = Field(default="comfy-workflow", pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    server: str | None = None
    render: bool = False


def install_comfy_routes(app, store):
    async def prepare(body):
        info = body.object_info
        if body.server and not info:
            from evosprig.integrations.comfy_client import ComfyClient

            try:
                info = await ComfyClient(body.server).object_info()
            except Exception:
                raise HTTPException(422, "could not read ComfyUI node schemas; check the server address") from None
        try:
            workflow = ComfyWorkflow(body.workflow, info)
            # Store only the node classes used by this document.
            info = {k: v for k, v in info.items() if any(workflow.class_type(n) == k for n in workflow.nodes)}
            bundle = import_comfy_spec(workflow, body.project_id, server=body.server if body.render else None)
            compile_snapshot(AgentSpec.model_validate(bundle["spec"]), {})
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise HTTPException(422, SECRET.sub("[redacted]", str(exc))[:1500]) from None
        return bundle, info

    @app.post("/api/comfy/inspect")
    async def inspect(body: ImportBody):
        bundle, _ = await prepare(body)
        return {"project_id": body.project_id, "node_count": len(bundle["node_map"]),
                "spec": bundle["spec"], "layout": bundle["layout"], "node_map": bundle["node_map"]}

    @app.post("/api/comfy/import", status_code=201)
    async def create(body: ImportBody):
        bundle, info = await prepare(body)
        integration = {k: bundle[k] for k in ("workflow", "node_map", "bindings")}
        integration["object_info"] = info
        return store.create(AgentSpec.model_validate(bundle["spec"]), bundle["layout"],
                            resources={}, identity=current_principal.get().key,
                            integrations={"comfy": integration})

    @app.get("/api/projects/{project_id}/comfy/export")
    async def export(project_id: str, format: str = "ui"):
        document = store.get(project_id, identity=current_principal.get().key)
        saved = store.integration(project_id, "comfy", identity=current_principal.get().key)
        if saved is None:
            raise HTTPException(404, "project has no imported ComfyUI workflow")
        if format not in {"ui", "api"}:
            raise HTTPException(422, "choose ui or api")
        workflow = ComfyWorkflow(saved["workflow"], saved["object_info"])
        current = document["spec"]["graph"]["nodes"]
        original_prompt = workflow.compile()
        try:
            for original, alias in saved["node_map"].items():
                if alias not in current:
                    if workflow.ui:
                        workflow.nodes[original]["mode"] = 2
                    else:
                        workflow.nodes.pop(original, None)
                    continue
                for name, value in current[alias]["inputs"].items():
                    if "value" in value:
                        workflow.disconnect(original, name).set_input(original, name, value["value"])
                    elif value.get("ref", "").startswith("nodes."):
                        _, source, _, port = value["ref"].split(".")
                        expected_id = next((key for key, val in saved["node_map"].items() if val == source), None)
                        prior = original_prompt[original]["inputs"].get(name)
                        if prior != [expected_id, int(port.removeprefix("output_"))]:
                            if expected_id is None:
                                raise ValueError("media connection has no corresponding ComfyUI node")
                            workflow.connect(original, name, expected_id, int(port.removeprefix("output_")))
                    else:
                        raise ValueError("resolve agent-generated media inputs by running the graph first")
                if workflow.ui and alias in document["layout"]:
                    pos = document["layout"][alias]
                    workflow.nodes[original]["pos"] = [pos["x"], pos["y"]]
            return deepcopy(workflow.export_ui() if format == "ui" else workflow.compile())
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, SECRET.sub("[redacted]", str(exc))[:1000]) from None
