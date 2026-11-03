"""ComfyUI inspection and conversion commands."""

import asyncio
import json
from pathlib import Path

import yaml

from evosprig.core.spec import AgentSpec, save_spec
from evosprig.integrations.comfyui import ComfyWorkflow
from evosprig.plugins.comfy_tools import import_comfy_spec


def add_commands(commands):
    parser = commands.add_parser("comfy", help="Import, inspect and export ComfyUI workflows")
    actions = parser.add_subparsers(dest="comfy_action", required=True)
    for name in ("inspect", "import", "export"):
        sub = actions.add_parser(name)
        sub.add_argument("workflow", type=Path)
        sub.add_argument("--schema", type=Path, help="Saved /object_info response")
        sub.add_argument("--server", help="ComfyUI base URL; fetch live node schemas")
        if name == "import":
            sub.add_argument("--id", default="comfy-workflow")
            sub.add_argument("--out", type=Path, required=True)
            sub.add_argument("--prepare-only", action="store_true", help="Build graph without submitting renders")
        if name == "export":
            sub.add_argument("--patch", type=Path, help="Node IDs mapped to inputs and/or enabled")
            sub.add_argument("--format", choices=["ui", "api"], default="ui")
            sub.add_argument("--out", type=Path, required=True)


def run_command(args):
    info = json.loads(args.schema.read_text()) if args.schema else {}
    if args.server:
        from evosprig.integrations.comfy_client import ComfyClient

        info = asyncio.run(ComfyClient(args.server).object_info())
    workflow = ComfyWorkflow(json.loads(args.workflow.read_text()), info)
    if args.comfy_action == "inspect":
        print(json.dumps({"format": "ui" if workflow.ui else "api", "nodes": workflow.describe()}, indent=2, ensure_ascii=False))
    elif args.comfy_action == "import":
        bundle = import_comfy_spec(workflow, args.id, server=None if args.prepare_only else args.server)
        args.out.mkdir(parents=True, exist_ok=False)
        save_spec(AgentSpec.model_validate(bundle["spec"]), args.out / "agent.yaml")
        (args.out / "deployment.yaml").write_text(yaml.safe_dump(bundle["bindings"], sort_keys=False))
        (args.out / "comfy-workflow.json").write_text(json.dumps(bundle["workflow"], ensure_ascii=False, indent=2))
        (args.out / "studio.json").write_text(json.dumps({"layout": bundle["layout"]}, indent=2))
        print(json.dumps({"project": args.id, "nodes": len(bundle["node_map"]), "directory": str(args.out)}))
    else:
        patch = json.loads(args.patch.read_text()) if args.patch else {}
        for key, change in patch.items():
            if set(change) - {"inputs", "enabled"}:
                raise ValueError("patch entries accept inputs and enabled")
            for name, value in change.get("inputs", {}).items():
                workflow.set_input(key, name, value)
            if "enabled" in change:
                if type(change["enabled"]) is not bool:
                    raise ValueError("enabled must be a boolean")
                workflow.set_enabled(key, change["enabled"])
        result = workflow.compile() if args.format == "api" else workflow.export_ui()
        with args.out.open("x") as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
        print(json.dumps({"output": str(args.out), "format": args.format}))
