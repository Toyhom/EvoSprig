"""Allowlisted, independently installable Python project export."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from pprint import pformat

import yaml

from evosprig import __version__
from evosprig.core.spec import canonical_json, save_spec
from evosprig.core.version import AgentVersion, check_public_text
from evosprig.plugins.builtin_tools import BUILTIN_NAMES
from evosprig.plugins.memory_tools import MEMORY_TOOL_NAMES

MODULES = (
    "__init__.py",
    "config.py",
    "data_cli.py",
    "core/__init__.py",
    "core/spec.py",
    "core/version.py",
    "core/protocols.py",
    "core/runtime.py",
    "core/engine.py",
    "core/journal.py",
    "core/expressions.py",
    "core/memory.py",
    "core/tool_policy.py",
    "sdk/__init__.py",
    "sdk/builder.py",
    "plugins/__init__.py",
    "plugins/mock.py",
    "plugins/builtin_tools.py",
    "plugins/openai_compatible.py",
    "plugins/sqlite_journal.py",
    "plugins/sqlite_memory.py",
    "plugins/sqlite_tools.py",
    "plugins/structured_memory.py",
    "plugins/episodic_memory.py",
    "plugins/semantic_memory.py",
    "plugins/embeddings.py",
    "plugins/memory_tools.py",
    "plugins/documents.py",
    "plugins/retrieval.py",
    "plugins/http_tools.py",
    "plugins/external_http.py",
    "plugins/mcp_tools.py",
)

APP = """import argparse
import asyncio
import json
from pathlib import Path

from evosprig.config import make_models, make_tools, restore_models
from evosprig.core.journal import Scope
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.core.runtime import Runtime
from evosprig.plugins.sqlite_journal import SQLiteJournal

parser = argparse.ArgumentParser(description="Run the exported EvoSprig agent")
inputs = parser.add_mutually_exclusive_group()
inputs.add_argument("--input", help="JSON input object")
inputs.add_argument("--input-file", type=Path, help="JSON task input file")
parser.add_argument("--mock", action="store_true")
parser.add_argument("--profile")
parser.add_argument("--workspace", type=Path)
parser.add_argument("--resume", help="Run ID to resume")
parser.add_argument("--path", help="Waiting input path")
parser.add_argument("--response", help="JSON human response")
parser.add_argument("--allow-writes", action="store_true")
parser.add_argument("--documents", type=Path, help="Load text documents into this application's workspace")
args = parser.parse_args()
root = Path(__file__).resolve().parent
spec = load_spec(root / "agent.yaml")
version = compile_agent(spec, root)
expected = json.loads((root / "agent.lock.json").read_text())
if version.lock != expected:
    raise SystemExit("Project changed: rebuild the export to update agent.lock.json")
workspace = args.workspace or root / ".evosprig"
if args.documents:
    if args.input or args.input_file or args.resume or args.path or args.response:
        parser.error("load documents separately from running or resuming the agent")
    from evosprig.data_cli import add_documents
    print(json.dumps(add_documents(args.documents, workspace, spec.id), indent=2))
    raise SystemExit(0)
journal = SQLiteJournal(workspace / "runs.sqlite")
if args.resume:
    record = journal.get(args.resume)
    if record["version"]["version_id"] != version.version_id:
        raise SystemExit("Run belongs to a different exported version")
    if bool(args.path) != bool(args.response):
        parser.error("--path and --response must be supplied together")
    if args.response:
        journal.respond(args.resume, args.path, json.loads(args.response))
    runtime = Runtime(restore_models(record["metadata"]["models"]), make_tools(workspace, Scope(spec.id), bindings=record["metadata"].get("tools", {})), journal=journal,
                      allow_writes=record["metadata"]["allow_writes"])
    result = asyncio.run(runtime.resume(args.resume))
else:
    if args.input is None and args.input_file is None:
        parser.error("provide --input for a new run")
    bindings = None if args.profile else json.loads((root / "tool-bindings.json").read_text())
    runtime = Runtime(make_models(spec, args.profile, args.mock), make_tools(workspace, Scope(spec.id), profile=args.profile, bindings=bindings), journal=journal,
                      allow_writes=args.allow_writes)
    result = asyncio.run(runtime.run(version, json.loads(args.input_file.read_text() if args.input_file else args.input)))
print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
raise SystemExit(1 if result.status in {"failed", "canceled"} else 0)
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
        f"    spec_version={spec.spec_version!r},",
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
        lines.append(f"builder.edge({edge.source!r}, {edge.target!r}, when={edge.when!r})")
    lines += [
        f"builder.output(**{pformat({key: value.model_dump() for key, value in spec.graph.output.items()}, sort_dicts=True)})",
        f"builder.execution(**{spec.execution.model_dump()!r})",
        "spec = builder.build_spec()",
        "",
    ]
    return "\n".join(lines)


def compatibility_report(
    version: AgentVersion, target: str = "python", *, tool_bindings=None
) -> dict:
    missing = []
    if target not in {"python", "http", "container"}:
        missing.append({"target": target, "reason": "target runtime is not implemented"})
    tool_bindings = tool_bindings or {}
    for name, binding in version.spec.tools.items():
        if binding.plugin in tool_bindings:
            config = tool_bindings[binding.plugin]
            if (
                config.get("kind") in {"http", "mcp", "external_http", "sqlite"}
                and config.get("version", "1") == binding.version
            ):
                continue
        if binding.plugin not in BUILTIN_NAMES | MEMORY_TOOL_NAMES or binding.version != "1":
            missing.append(
                {"tool": name, "plugin": binding.plugin, "reason": "plugin has no bundled exporter"}
            )
    return {
        "target": target,
        "compatible": not missing,
        "missing": missing,
        "external_services": sorted({item.binding for item in version.spec.models.values()}),
        "external_tools": sorted(tool_bindings),
        "runtime": __version__,
        "agent_version": version.version_id,
    }


def export_python(
    version: AgentVersion, destination: str | Path, *, target: str = "python", tool_bindings=None
) -> dict:
    # Validate and include only the declared bindings, never unrelated deployment data.
    bindings = {}
    for tool in version.spec.tools.values():
        if tool.plugin in (tool_bindings or {}):
            raw = tool_bindings[tool.plugin]
            if raw.get("kind") == "http":
                from evosprig.plugins.http_tools import HTTPToolConfig

                config = HTTPToolConfig.model_validate(raw)
            elif raw.get("kind") == "external_http":
                from evosprig.plugins.external_http import ExternalHTTPConfig

                config = ExternalHTTPConfig.model_validate(raw)
            elif raw.get("kind") == "mcp":
                from evosprig.plugins.mcp_tools import MCPToolConfig

                config = MCPToolConfig.model_validate(raw)
            elif raw.get("kind") == "sqlite":
                from evosprig.plugins.sqlite_tools import SQLiteToolConfig

                config = SQLiteToolConfig.model_validate(raw)
            else:
                raise ValueError("tool plugin has no bundled exporter")
            if config.name != tool.plugin:
                raise ValueError("tool binding name mismatch")
            bindings[tool.plugin] = config.model_dump(mode="json")
    report = compatibility_report(version, target, tool_bindings=bindings)
    if not report["compatible"]:
        raise ValueError(canonical_json(report))
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("export destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".evosprig-export-", dir=destination.parent))
    try:
        root = Path(__file__).resolve().parents[1]
        modules = MODULES + (
            ("server/__init__.py", "server/worker.py", "server/standalone.py")
            if target != "python"
            else ()
        )
        for module in modules:
            output = staging / "src" / "evosprig" / module
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes((root / module).read_bytes())
        save_spec(version.spec, staging / "agent.yaml")
        files = {
            "app.py": APP,
            "LICENSE": (Path(__file__).parent / "LICENSE").read_text(),
            "NOTICE": "EvoSprig\nCopyright 2026 EvoSprig contributors\n",
            "tool-bindings.json": json.dumps(bindings, indent=2) + "\n",
            "build_agent.py": builder_source(version),
            "agent.lock.json": json.dumps(version.lock, indent=2) + "\n",
            "export-report.json": json.dumps(report, indent=2) + "\n",
            "requirements.lock": (Path(__file__).parent / "runtime.lock").read_text(),
            ".env.example": "DEEPSEEK_API_KEY=\nEVOSPRIG_BASE_URL=https://api.deepseek.com\nEVOSPRIG_MODEL=deepseek-flash\n",
            "deployment.example.yaml": yaml.safe_dump(
                {
                    "models": {
                        name: {
                            "base_url": "https://api.deepseek.com",
                            "model": "deepseek-flash",
                            "api_key_env": "DEEPSEEK_API_KEY",
                            "options": {"thinking": {"type": "disabled"}},
                        }
                        for name in report["external_services"]
                    },
                    "tools": bindings,
                },
                sort_keys=False,
            ),
            "pyproject.toml": '[build-system]\nrequires = ["hatchling==1.27.0"]\nbuild-backend = "hatchling.build"\n\n[project]\nname = "evosprig-export-runtime"\nversion = "0.1.0"\nrequires-python = ">=3.12"\nlicense = "Apache-2.0"\nlicense-files = ["LICENSE", "NOTICE"]\ndependencies = ["pydantic==2.12.3", "jsonschema==4.25.1", "PyYAML==6.0.3", "httpx==0.28.1"]\n\n[tool.hatch.build.targets.wheel]\npackages = ["src/evosprig"]\n',
            "README.md": "# Exported EvoSprig application\n\nCreate a Python 3.12+ environment, then run:\n\n```bash\npython -m pip install -r requirements.lock\npython -m pip install --no-deps .\npython app.py --mock --input '<JSON matching agent.yaml input_schema>'\n```\n\nFor live calls, set DEEPSEEK_API_KEY and omit --mock. Use --profile deployment.example.yaml for explicit bindings. Runtime sources are bundled; installation and execution use no Studio or control plane. Review export-report.json for required external services. The selected version is fixed in agent.lock.json.\n\nFor document applications, load your own text collection with `python app.py --documents ./notes --workspace ./workspace`. Use the same `--workspace` for subsequent runs or the HTTP service. Exports do not contain your database or memory records.\n",
            "DEPENDENCIES.md": "# Dependencies\n\nPydantic (MIT), jsonschema (MIT), PyYAML (MIT), HTTPX (BSD-3-Clause), Hatchling build tooling (MIT). The lock records exact versions. Dependencies are installed separately with their original license metadata.\n",
        }
        if any(binding["kind"] == "mcp" for binding in bindings.values()):
            files["requirements.lock"] += (Path(__file__).parent / "mcp.lock").read_text()
        if target != "python":
            files["requirements.lock"] += (Path(__file__).parent / "server.lock").read_text()
            files["serve.py"] = SERVICE
            files["README.md"] += SERVICE_README
        if target == "container":
            files["Dockerfile"] = DOCKERFILE
            files[".dockerignore"] = (
                "**\n!src/**\n!agent.yaml\n!agent.lock.json\n!tool-bindings.json\n!serve.py\n!requirements.lock\n!pyproject.toml\n!LICENSE\n!NOTICE\n"
                + "".join(
                    "!" + resource.path + "\n" for resource in version.spec.resources.values()
                )
            )
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


SERVICE = """import argparse
import os
from pathlib import Path
import uvicorn
from evosprig.server.standalone import create_service

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--workspace", type=Path, default=Path(".evosprig"))
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    app = create_service(Path(__file__).resolve().parent, args.workspace,
                         token=os.environ.get("EVOSPRIG_SERVICE_TOKEN"), profile=args.profile,
                         mock=args.mock, allow_writes=args.allow_writes, concurrency=args.concurrency)
    uvicorn.run(app, host=args.host, port=args.port, access_log=False)
"""

SERVICE_README = """
## HTTP service

Set `EVOSPRIG_SERVICE_TOKEN` to a secret, then run `python serve.py --mock`.
The service listens on loopback port 8080. Use `--profile deployment.yaml` for live
models, `--workspace PATH` for persistent SQLite, and `--concurrency N` for its bounded
worker pool. Writes require both the spec policy and operator `--allow-writes`.

Send `Authorization: Bearer <token>` to `POST /runs` with `{"input": {...}}`.
Poll `GET /runs/{run_id}`, read `/runs/{run_id}/events` (SSE, Last-Event-ID),
submit `POST /runs/{run_id}/input` with `{"path": "...", "response": {...}}`, or
`POST /runs/{run_id}/cancel`. Restarting the service resumes queued/checkpointed runs.
This is a single-agent, single-trust-domain service. Use a separate workspace per
exported version. Put TLS at a reverse proxy for remote access; browser origins are
rejected. `/health` is public and contains no run data.

## Container target

When a Dockerfile is present: `docker build -t my-agent .`, then
`docker run --rm -p 127.0.0.1:8080:8080 -e EVOSPRIG_SERVICE_TOKEN -e DEEPSEEK_API_KEY
-v evosprig-state:/state my-agent --host 0.0.0.0 --workspace /state --mock`.
Remove `--mock` for live calls. The image runs as UID 10001. Credentials, runtime
history and model weights are not build inputs. The Python base image is tag-pinned;
pin its digest in your deployment registry for immutable rebuilds.
"""

DOCKERFILE = """FROM python:3.12.12-slim
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY . .
RUN python -m pip install --no-cache-dir --no-deps . && mkdir /state && chown 10001:10001 /state
USER 10001:10001
EXPOSE 8080
VOLUME ["/state"]
ENTRYPOINT ["python", "serve.py"]
CMD ["--host", "0.0.0.0", "--workspace", "/state"]
"""
