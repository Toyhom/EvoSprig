"""Configure, run and reopen the supplied applications with EvoSprig's native CLI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml
from jsonschema import validate

from evosprig.config import make_models, read_profile
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.data_cli import add_documents, load_csv
from evosprig.exporters.python import export_python
from evosprig.plugins.openai_compatible import Connection

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def settings(name):
    catalog = json.loads((EXAMPLES / "quickstarts.json").read_text())
    if name not in catalog:
        raise ValueError("Unknown application; choose: " + ", ".join(sorted(catalog)))
    return catalog[name]


def configure(name, workspace, *, base_url=None, model=None, key_env=None):
    item = settings(name)
    root = EXAMPLES / name
    spec = load_spec(root / item.get("spec", "agent.yaml"))
    workspace.mkdir(parents=True, exist_ok=True)
    profile_path = workspace / "deployment.yaml"
    if not profile_path.exists():
        profile = read_profile(root / item["profile"]) if "profile" in item else {"models": {}}
        for binding in {entry.binding for entry in spec.models.values()}:
            profile["models"].setdefault(binding, {
                "base_url": "https://api.deepseek.com", "model": "deepseek-flash",
                "api_key_env": "DEEPSEEK_API_KEY", "timeout_seconds": 180,
                "options": {"thinking": {"type": "disabled"}},
            })
        if bool(base_url) != bool(model):
            raise ValueError("Supply --base-url and --model together")
        for binding, value in profile["models"].items():
            if base_url:
                requires = sorted({cap for entry in spec.models.values()
                                   if entry.binding == binding for cap in entry.requires})
                value = {"base_url": base_url, "model": model,
                         "api_key_env": key_env or "MODEL_API_KEY", "capabilities": requires,
                         "timeout_seconds": 180, "json_mode": "without_tools"}
                profile["models"][binding] = value
            elif key_env:
                value["api_key_env"] = key_env
            Connection.model_validate(value)
        profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    elif base_url or model or key_env:
        raise ValueError(f"Configuration exists; edit {profile_path} or choose a new --workspace")
    sample = root / item.get("sample", "sample.json")
    data = json.loads(sample.read_text())
    validate(data, spec.input_schema)
    input_path = workspace / "input.json"
    if not input_path.exists():
        input_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if item.get("documents"):
        add_documents(root / item["documents"], workspace, spec.id)
    if item.get("csv") and not (workspace / "shop.sqlite").exists():
        load_csv(root / item["csv"], workspace / "shop.sqlite", "orders")
    return {"profile": str(profile_path), "input": str(input_path), "workspace": str(workspace)}


def package(name, workspace, destination):
    item = settings(name)
    root = EXAMPLES / name
    spec = load_spec(root / item.get("spec", "agent.yaml"))
    profile = read_profile(workspace / "deployment.yaml")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Export only declared application resources and tool contracts, never workspace data.
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        folder = Path(temporary) / "application"
        export_python(compile_agent(spec, root), folder, tool_bindings=profile.get("tools", {}))
        with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(folder).as_posix())
    return str(destination)


def command(name, action, workspace, *, input_file=None, allow_writes=False, port=18766,
            workbench=False):
    item = settings(name)
    root = EXAMPLES / name
    spec_path = root / item.get("spec", "agent.yaml")
    profile = workspace / "deployment.yaml"
    if not profile.is_file():
        raise ValueError(f"Run python examples/quickstart.py {name} setup first")
    spec = load_spec(spec_path)
    for provider in make_models(spec, profile).values():
        if not os.environ.get(provider.connection.api_key_env):
            raise ValueError("Set " + provider.connection.api_key_env + " before starting")
    if name == "data-analyst":
        os.environ.setdefault("EVOSPRIG_SQLITE_PATH", str(workspace / "shop.sqlite"))
    bindings = read_profile(profile).get("tools", {})
    for binding in bindings.values():
        for field in ("auth_env", "path_env", "repository_env"):
            if binding.get(field) and not os.environ.get(binding[field]):
                raise ValueError("Set " + binding[field] + " before starting")
    cli = [sys.executable, "-m", "evosprig.cli"]
    common = ["--profile", str(profile), "--workspace", str(workspace)]
    if action == "run":
        source = input_file or workspace / "input.json"
        validate(json.loads(source.read_text()), spec.input_schema)
        return [*cli, "run", str(spec_path), *common, "--input-file", str(source),
                *(["--allow-writes"] if allow_writes else [])]
    studio = ROOT / ("apps/cowork" if workbench and name == "cowork" else "apps/studio/dist")
    if not (studio / "index.html").is_file():
        raise ValueError("Build Studio first: npm --prefix apps/studio ci && "
                         "npm --prefix apps/studio run build")
    return [*cli, "serve", "--project", str(spec_path), *common,
            "--studio-dir", str(studio), "--port", str(port)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("application", choices=sorted(json.loads((EXAMPLES / "quickstarts.json").read_text())))
    parser.add_argument("action", choices=["setup", "run", "studio", "pack"])
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--key-env")
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--workbench", action="store_true", help="Open Cowork's application UI")
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument("--out", type=Path, help="New ZIP path for pack")
    args = parser.parse_args()
    workspace = (args.workspace or ROOT / ".evosprig/examples" / args.application).resolve()
    try:
        if args.action == "setup":
            print(json.dumps(configure(args.application, workspace, base_url=args.base_url,
                                       model=args.model, key_env=args.key_env), indent=2))
        elif args.action == "pack":
            if not args.out:
                parser.error("pack requires --out application.zip")
            print(package(args.application, workspace, args.out.resolve()))
        else:
            argv = command(args.application, args.action, workspace, input_file=args.input_file,
                           allow_writes=args.allow_writes, port=args.port, workbench=args.workbench)
            raise SystemExit(subprocess.call(argv, cwd=ROOT))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
