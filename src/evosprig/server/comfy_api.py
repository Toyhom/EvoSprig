"""ComfyUI import and roundtrip export for Studio."""

from copy import deepcopy

from fastapi import HTTPException
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import Field

from evosprig.config import read_profile
from evosprig.core.spec import AgentSpec, Contract, digest
from evosprig.core.version import SECRET, compile_snapshot
from evosprig.integrations.comfyui import ComfyWorkflow, fields, input_schema
from evosprig.plugins.comfy_tools import ComfyRecipeConfig, comfy_recipe_tool, import_comfy_spec
from evosprig.plugins.sqlite_projects import RevisionConflict

from .auth import current_principal


class ImportBody(Contract):
    workflow: dict
    object_info: dict = Field(default_factory=dict)
    project_id: str = Field(default="comfy-workflow", pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    server: str | None = None
    render: bool = False


class RecipePatch(Contract):
    revision: int = Field(ge=1)
    workflow_hash: str
    changes: dict = Field(default_factory=dict)


def install_comfy_routes(app, store, *, profile=None):
    def recipes(project_id):
        doc = store.get(project_id, identity=current_principal.get().key)
        configured = read_profile(profile)
        allowed = {tool["plugin"] for tool in doc["spec"]["tools"].values()}
        saved = store.integration(project_id, "comfy_recipes", identity=current_principal.get().key) or {}
        found = {name: {**binding, "workflow": saved.get(name, binding["workflow"])}
                 for name, binding in (configured or {}).get("tools", {}).items()
                 if name in allowed and binding.get("kind") == "comfy_recipe"}
        return doc, found, saved

    def recipe(project_id, name):
        doc, found, saved = recipes(project_id)
        if name not in found:
            raise HTTPException(404, "render recipe not found")
        return doc, ComfyRecipeConfig.model_validate(found[name]), saved

    @app.get("/api/projects/{project_id}/recipes")
    async def list_recipes(project_id: str):
        _, found, _ = recipes(project_id)
        return [{"name": name, "node_count": len(ComfyWorkflow(binding["workflow"], binding["object_info"]).nodes)}
                for name, binding in found.items()]

    @app.get("/api/projects/{project_id}/recipes/{name}")
    async def get_recipe(project_id: str, name: str):
        doc, config, _ = recipe(project_id, name)
        workflow = ComfyWorkflow(config.workflow, config.object_info)
        classes = {workflow.class_type(node) for node in workflow.nodes}
        return {"name": name, "revision": doc["revision"], "workflow": workflow.export(),
                "workflow_hash": digest(config.workflow), "outputs": config.outputs,
                "nodes": [{"id": node, "class_type": workflow.class_type(node),
                           "title": value.get("title", workflow.class_type(node)), "mode": value.get("mode", 0),
                           "position": value.get("pos", [index * 300, 0]),
                           "input_schemas": {key: input_schema(descriptor) for key, descriptor, _ in
                                             fields(config.object_info.get(workflow.class_type(node), {}),
                                                    {k: v[0] for k, v in workflow._widgets(node).items()}
                                                    if workflow.ui and workflow.class_type(node) in config.object_info else value.get("inputs", {}))},
                           "inputs": {k: v[0] for k, v in workflow._widgets(node).items()}
                           if workflow.ui and workflow.class_type(node) in config.object_info else value.get("inputs", {})}
                          for index, (node, value) in enumerate(workflow.nodes.items())],
                "object_info": {k: v for k, v in config.object_info.items() if k in classes}}

    @app.post("/api/projects/{project_id}/recipes/{name}")
    async def edit_recipe(project_id: str, name: str, body: RecipePatch):
        _, config, saved = recipe(project_id, name)
        if digest(config.workflow) != body.workflow_hash:
            raise HTTPException(409, "render graph changed; reload before saving")
        workflow = ComfyWorkflow(config.workflow, config.object_info)
        try:
            for node, changes in body.changes.items():
                if not isinstance(changes, dict) or changes.keys() - {"inputs", "enabled"}:
                    raise ValueError("choose inputs or enabled for each node")
                if "enabled" in changes:
                    if type(changes["enabled"]) is not bool:
                        raise ValueError("enabled must be a boolean")
                    workflow.set_enabled(node, changes["enabled"])
                for field, value in changes.get("inputs", {}).items():
                    workflow.set_input(node, field, value)
            updated = config.model_copy(update={"workflow": workflow.export()})
            # Validate both editable controls and the actual executable graph.
            comfy_recipe_tool(updated)
            workflow.compile(config.outputs)
            document = store.update_integration(project_id, "comfy_recipes", {**saved, name: workflow.export()},
                                                body.revision, identity=current_principal.get().key)
            return {"project": document, "workflow_hash": digest(workflow.export())}
        except RevisionConflict as exc:
            raise HTTPException(409, str(exc)) from None
        except (ValueError, TypeError, KeyError, SchemaValidationError) as exc:
            raise HTTPException(422, SECRET.sub("[redacted]", str(exc))[:1000]) from None

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
