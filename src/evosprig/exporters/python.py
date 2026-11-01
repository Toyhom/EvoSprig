"""Allowlisted, independently installable Python project export."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from pprint import pformat

from evosprig import __version__
from evosprig.core.spec import canonical_json, save_spec
from evosprig.core.version import AgentVersion, check_public_text
from evosprig.plugins.builtin_tools import BUILTIN_NAMES

MODULES = (
    "__init__.py",
    "config.py",
    "core/__init__.py",
    "core/spec.py",
    "core/version.py",
    "core/protocols.py",
    "core/runtime.py",
    "sdk/__init__.py",
    "sdk/builder.py",
    "plugins/__init__.py",
    "plugins/mock.py",
    "plugins/builtin_tools.py",
    "plugins/openai_compatible.py",
)

APP = """import argparse
import asyncio
import json
from pathlib import Path

from evosprig.config import make_models
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.core.runtime import Runtime
from evosprig.plugins.builtin_tools import builtin_registry

parser = argparse.ArgumentParser(description="Run the exported EvoSprig agent")
parser.add_argument("--input", required=True, help="JSON input object")
parser.add_argument("--mock", action="store_true")
parser.add_argument("--profile")
args = parser.parse_args()
root = Path(__file__).resolve().parent
spec = load_spec(root / "agent.yaml")
version = compile_agent(spec, root)
expected = json.loads((root / "agent.lock.json").read_text())
if version.lock != expected:
    raise SystemExit("Project changed: rebuild the export to update agent.lock.json")
runtime = Runtime(make_models(spec, args.profile, args.mock), builtin_registry())
result = asyncio.run(runtime.run(version, json.loads(args.input)))
print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
raise SystemExit(0 if result.status == "succeeded" else 1)
"""


def builder_source(version: AgentVersion) -> str:
    spec = version.spec
    lines = [
        "from evosprig.sdk import Builder",
        "",
        "builder = Builder(",
        f"    {spec.id!r},",
        f"    {pformat(spec.input_schema, sort_dicts=True)},",
        f"    {pformat(spec.output_schema, sort_dicts=True)},",
        ")",
    ]
    for name, model in spec.models.items():
        lines.append(f"builder.model({name!r}, {model.binding!r}, {model.requires!r})")
    for name, tool in spec.tools.items():
        lines.append(f"builder.tool({name!r}, {tool.plugin!r}, {tool.version!r})")
    for name, resource in spec.resources.items():
        lines.append(f"builder.resource({name!r}, {resource.path!r}, {resource.role!r})")
    for name, node in spec.graph.nodes.items():
        config = node.model_dump(exclude={"type"}, exclude_none=True)
        lines.append(
            f"builder.node({name!r}, {node.type!r}, entry={name == spec.graph.entry!r}, **{pformat(config, sort_dicts=True)})"
        )
    for edge in sorted(spec.graph.edges, key=lambda edge: (edge.source, edge.target)):
        lines.append(f"builder.edge({edge.source!r}, {edge.target!r})")
    lines += [
        f"builder.output(**{pformat({key: value.model_dump() for key, value in spec.graph.output.items()}, sort_dicts=True)})",
        f"builder.execution(**{spec.execution.model_dump()!r})",
        "spec = builder.build_spec()",
        "",
    ]
    return "\n".join(lines)


def compatibility_report(version: AgentVersion, target: str = "python") -> dict:
    missing = []
    if target != "python":
        missing.append({"target": target, "reason": "target runtime is not implemented"})
    for name, binding in version.spec.tools.items():
        if binding.plugin not in BUILTIN_NAMES or binding.version != "1":
            missing.append(
                {"tool": name, "plugin": binding.plugin, "reason": "plugin has no bundled exporter"}
            )
    return {
        "target": target,
        "compatible": not missing,
        "missing": missing,
        "external_services": sorted({item.binding for item in version.spec.models.values()}),
        "runtime": __version__,
        "agent_version": version.version_id,
    }


def export_python(
    version: AgentVersion, destination: str | Path, *, target: str = "python"
) -> dict:
    report = compatibility_report(version, target)
    if not report["compatible"]:
        raise ValueError(canonical_json(report))
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("export destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".evosprig-export-", dir=destination.parent))
    try:
        root = Path(__file__).resolve().parents[1]
        for module in MODULES:
            output = staging / "src" / "evosprig" / module
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes((root / module).read_bytes())
        save_spec(version.spec, staging / "agent.yaml")
        files = {
            "app.py": APP,
            "build_agent.py": builder_source(version),
            "agent.lock.json": json.dumps(version.lock, indent=2) + "\n",
            "export-report.json": json.dumps(report, indent=2) + "\n",
            "requirements.lock": (Path(__file__).parent / "runtime.lock").read_text(),
            ".env.example": "DEEPSEEK_API_KEY=\nEVOSPRIG_BASE_URL=https://api.deepseek.com\nEVOSPRIG_MODEL=deepseek-flash\n",
            "deployment.example.yaml": "models:\n"
            + "".join(
                f"  {name}:\n    base_url: https://api.deepseek.com\n    model: deepseek-flash\n    api_key_env: DEEPSEEK_API_KEY\n    options:\n      thinking: {{type: disabled}}\n"
                for name in report["external_services"]
            ),
            "pyproject.toml": '[build-system]\nrequires = ["hatchling==1.27.0"]\nbuild-backend = "hatchling.build"\n\n[project]\nname = "evosprig-export-runtime"\nversion = "0.1.0.dev0"\nrequires-python = ">=3.12"\ndependencies = ["pydantic==2.12.3", "jsonschema==4.25.1", "PyYAML==6.0.3", "httpx==0.28.1"]\n\n[tool.hatch.build.targets.wheel]\npackages = ["src/evosprig"]\n',
            "README.md": "# Exported EvoSprig application\n\nCreate a Python 3.12+ environment, then run:\n\n```bash\npython -m pip install -r requirements.lock\npython -m pip install --no-deps .\npython app.py --mock --input '<JSON matching agent.yaml input_schema>'\n```\n\nFor live calls, set DEEPSEEK_API_KEY and omit --mock. Use --profile deployment.example.yaml for explicit bindings. Runtime sources are bundled; installation and execution use no Studio or control plane. Review export-report.json for required external services. The selected version is fixed in agent.lock.json.\n",
            "THIRD_PARTY_NOTICES.md": "# Dependencies\n\nPydantic (MIT), jsonschema (MIT), PyYAML (MIT), HTTPX (BSD-3-Clause), Hatchling build tooling (MIT). The lock records exact versions. Dependencies are installed separately with their original license metadata.\n",
        }
        for name, content in files.items():
            (staging / name).write_text(content, encoding="utf-8")
        for name, resource in version.spec.resources.items():
            path = staging / resource.path
            if resource.path.split("/")[0] in {"src", "tests"} or path.exists():
                raise ValueError(f"resource path collides with exported runtime: {resource.path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(version.resources[name], encoding="utf-8")
        manifest = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                check_public_text(path.read_text(encoding="utf-8"))
                manifest[path.relative_to(staging).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staging.rename(destination)
        return report | {
            "files": len(manifest) + 1,
            "bytes": sum(path.stat().st_size for path in destination.rglob("*") if path.is_file()),
        }
    except BaseException:
        shutil.rmtree(staging)
        raise
