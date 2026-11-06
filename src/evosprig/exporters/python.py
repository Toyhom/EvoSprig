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
from evosprig.plugins.memory_banks import MemoryBanksConfig, plugin_bank
from evosprig.plugins.memory_tools import MEMORY_TOOL_NAMES
from evosprig.plugins.message_tools import MESSAGE_TOOL_NAMES
from evosprig.plugins.workspace_tools import WORKSPACE_TOOL_NAMES

MODULES = (
    "__init__.py",
    "config.py",
    "local_services.py", "process_support.py",
    "core/context_window.py",
    "data_cli.py",
    "core/__init__.py",
    "core/spec.py",
    "core/version.py",
    "core/protocols.py",
    "core/runtime.py",
    "core/triggers.py",
    "core/model_sessions.py",
    "core/multimodal.py",
    "core/engine.py",
    "core/json_program.py",
    "core/journal.py",
    "core/expressions.py",
    "core/memory.py",
    "core/tool_policy.py",
    "core/tool_context.py",
    "core/skills.py",
    "sdk/__init__.py",
    "sdk/builder.py",
    "plugins/__init__.py",
    "plugins/artifact_tools.py",
    "plugins/office_artifacts.py",
    "plugins/spice_artifacts.py",
    "plugins/comic_artifacts.py",
    "plugins/mock.py",
    "plugins/builtin_tools.py",
    "plugins/openai_compatible.py",
    "plugins/sqlite_journal.py",
    "plugins/sqlite_checkpoint.py",
    "plugins/sqlite_memory.py",
    "plugins/sqlite_tools.py",
    "plugins/repository_tools.py",
    "plugins/structured_memory.py",
    "plugins/episodic_memory.py",
    "plugins/semantic_memory.py",
    "plugins/embeddings.py",
    "plugins/memory_tools.py",
    "plugins/memory_banks.py",
    "plugins/workspace_tools.py",
    "plugins/message_tools.py",
    "plugins/python_tool.py",
    "plugins/documents.py",
    "plugins/document_library.py",
    "plugins/retrieval.py",
    "plugins/http_tools.py",
    "plugins/external_http.py",
    "plugins/mcp_tools.py",
    "plugins/comfy_tools.py",
    "integrations/__init__.py",
    "integrations/comfyui.py",
    "integrations/comfy_client.py",
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
parser.add_argument("--model-contract", action="store_true", help="Print required model roles without loading a model")
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
if args.model_contract:
    from evosprig.config import model_contract
    print(json.dumps(model_contract(spec), indent=2))
    raise SystemExit(0)
workspace = args.workspace or root / ".evosprig"
memory_config = json.loads((root / "memory-config.json").read_text())
if args.documents:
    if args.input or args.input_file or args.resume or args.path or args.response:
        parser.error("load documents separately from running or resuming the agent")
    from evosprig.data_cli import add_documents
    print(json.dumps(add_documents(args.documents, workspace, spec.id, profile=args.profile), indent=2))
    raise SystemExit(0)
journal = SQLiteJournal(workspace / "runs.sqlite")
if args.profile and not args.mock:
    from evosprig.local_services import prepare_services
    prepare_services(args.profile)
if args.resume:
    record = journal.get(args.resume)
    if record["version"]["version_id"] != version.version_id:
        raise SystemExit("Run belongs to a different exported version")
    if bool(args.path) != bool(args.response):
        parser.error("--path and --response must be supplied together")
    if args.response:
        journal.respond(args.resume, args.path, json.loads(args.response))
    runtime = Runtime(restore_models(record["metadata"]["models"]), make_tools(workspace, Scope(spec.id), profile=args.profile, bindings=record["metadata"].get("tools", {}), memory_config=memory_config), journal=journal,
                      allow_writes=record["metadata"]["allow_writes"])
    result = asyncio.run(runtime.resume(args.resume))
else:
    if args.input is None and args.input_file is None:
        parser.error("provide --input for a new run")
    bindings = None if args.profile else json.loads((root / "tool-bindings.json").read_text())
    runtime = Runtime(make_models(spec, args.profile, args.mock), make_tools(workspace, Scope(spec.id), profile=args.profile, bindings=bindings, memory_config=memory_config), journal=journal,
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
                config.get("kind") in {"artifact", "http", "mcp", "external_http", "sqlite", "repository", "comfy_node", "comfy_collect", "comfy_job", "comfy_recipe", "comfy_recipe_info"}
                and config.get("version", "1") == binding.version
            ):
                continue
        if plugin_bank(binding.plugin) is not None and binding.version == "1":
            continue
        if (
            binding.plugin
            not in BUILTIN_NAMES
            | MEMORY_TOOL_NAMES
            | WORKSPACE_TOOL_NAMES
            | MESSAGE_TOOL_NAMES
            | {"code.python"}
            or binding.version != "1"
        ):
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
    version: AgentVersion, destination: str | Path, *, target: str = "python", tool_bindings=None, document_config=None, memory_config=None
) -> dict:
    from evosprig.plugins.document_library import DocumentConfig

    document_config = DocumentConfig.model_validate(document_config or {}).model_dump()
    configured_memory = MemoryBanksConfig.model_validate(memory_config or {})
    selected_banks = {bank for tool in version.spec.tools.values() if (bank := plugin_bank(tool.plugin)) is not None}
    for tool in version.spec.tools.values():
        bank = plugin_bank(tool.plugin)
        if bank is not None:
            if bank not in configured_memory.banks:
                raise ValueError(f"memory bank {bank} needs deployment configuration")
            if tool.plugin.split(".")[-1] in {"write", "remember", "summarize"} and not configured_memory.banks[bank].agent_writes:
                raise ValueError(f"memory bank {bank} disables agent writes")
    memory_config = {"banks": {name: value.model_dump() for name, value in configured_memory.banks.items() if name in selected_banks}}

    # Validate and include only the declared bindings, never unrelated deployment data.
    bindings = {}
    for tool in version.spec.tools.values():
        if tool.plugin in (tool_bindings or {}):
            raw = tool_bindings[tool.plugin]
            if raw.get("kind") == "artifact":
                from evosprig.plugins.artifact_tools import ArtifactToolConfig

                config = ArtifactToolConfig.model_validate(raw)
            elif raw.get("kind") == "http":
                from evosprig.plugins.http_tools import HTTPToolConfig

                config = HTTPToolConfig.model_validate(raw)
            elif raw.get("kind") == "external_http":
                from evosprig.plugins.external_http import ExternalHTTPConfig

                config = ExternalHTTPConfig.model_validate(raw)
            elif raw.get("kind") == "mcp":
                from evosprig.plugins.mcp_tools import MCPToolConfig

                config = MCPToolConfig.model_validate(raw)
            elif raw.get("kind") == "repository":
                from evosprig.plugins.repository_tools import RepositoryToolConfig

                config = RepositoryToolConfig.model_validate(raw)
            elif raw.get("kind") == "sqlite":
                from evosprig.plugins.sqlite_tools import SQLiteToolConfig

                config = SQLiteToolConfig.model_validate(raw)
            elif raw.get("kind") == "comfy_collect":
                from evosprig.plugins.comfy_tools import ComfyCollectConfig

                config = ComfyCollectConfig.model_validate(raw)
            elif raw.get("kind") == "comfy_node":
                from evosprig.plugins.comfy_tools import ComfyNodeConfig

                config = ComfyNodeConfig.model_validate(raw)
            elif raw.get("kind") in {"comfy_recipe", "comfy_recipe_info"}:
                from evosprig.plugins.comfy_tools import ComfyRecipeConfig

                config = ComfyRecipeConfig.model_validate(raw)
            elif raw.get("kind") == "comfy_job":
                from evosprig.plugins.comfy_tools import ComfyJobConfig

                config = ComfyJobConfig.model_validate(raw)
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
            ("server/__init__.py", "server/worker.py", "server/standalone.py", "server/document_api.py")
            if target != "python"
            else ()
        )
        for module in modules:
            output = staging / "src" / "evosprig" / module
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes((root / module).read_bytes())
        save_spec(version.spec, staging / "agent.yaml")
        requirements = {}
        for connection in version.spec.models.values():
            requirements.setdefault(connection.binding, set()).update(connection.requires)
        model_examples = {}
        for name, capabilities in requirements.items():
            vision = "vision" in capabilities
            model_examples[name] = {
                "base_url": "https://your-provider.example/v1",
                "model": "your-vision-model" if vision else "your-text-model",
                "api_key_env": "MODEL_API_KEY",
                "capabilities": sorted(capabilities),
            }
        from evosprig.config import model_contract

        files = {
            "model-contract.json": json.dumps(model_contract(version.spec), indent=2) + "\n",
            "app.py": APP,
            "LICENSE": (Path(__file__).parent / "LICENSE").read_text(),
            "NOTICE": "EvoSprig\nCopyright 2026 EvoSprig contributors\n",
            "tool-bindings.json": json.dumps(bindings, indent=2) + "\n",
            "memory-config.json": json.dumps(memory_config, indent=2) + "\n",
            "build_agent.py": builder_source(version),
            "agent.lock.json": json.dumps(version.lock, indent=2) + "\n",
            "export-report.json": json.dumps(report, indent=2) + "\n",
            "requirements.lock": (Path(__file__).parent / "runtime.lock").read_text(),
            ".env.example": "MODEL_API_KEY=\nEVOSPRIG_SERVICE_TOKEN=\n",
            "deployment.example.yaml": yaml.safe_dump(
                {
                    "models": model_examples,
                    "tools": bindings,
                    "documents": document_config,
                    "memory": memory_config,
                },
                sort_keys=False,
            ),
            "pyproject.toml": '[build-system]\nrequires = ["hatchling==1.27.0"]\nbuild-backend = "hatchling.build"\n\n[project]\nname = "evosprig-export-runtime"\nversion = "0.1.0"\nrequires-python = ">=3.12"\nlicense = "Apache-2.0"\nlicense-files = ["LICENSE", "NOTICE"]\ndependencies = ["pydantic==2.12.3", "jsonschema==4.25.1", "PyYAML==6.0.3", "httpx==0.28.1"]\n\n[tool.hatch.build.targets.wheel]\npackages = ["src/evosprig"]\n',
            "README.md": "# Exported EvoSprig application\n\nCreate a Python 3.12+ environment, then run:\n\n```bash\npython -m pip install -r requirements.lock\npython -m pip install --no-deps .\npython app.py --mock --input '<JSON matching agent.yaml input_schema>'\n```\n\nThe application operator configures models once for all users. Inspect `model-contract.json` or run `python app.py --model-contract` to see the required roles and capabilities before deploying a model. Copy deployment.example.yaml to deployment.yaml and bind each role to an OpenAI-compatible API: set its URL, model ID and API-key environment variable. Use `api_key_env: null` for a service without authentication; opt in to `allow_http: true` for a self-hosted HTTP server outside loopback. Pass --profile deployment.yaml and omit --mock. Change the deployment file to switch model services without editing or exporting the agent again. End users send task input to the application; model credentials stay with its operator. Vision bindings need a model that accepts images. Set environment variables in your terminal; .env.example is a template. Runtime sources are bundled; installation and execution use no Studio or control plane. Review export-report.json for required external services. The selected version is fixed in agent.lock.json.\n\nFor document applications, load files with `python app.py --documents ./notes --profile deployment.yaml --workspace ./workspace`. Install `requirements-documents.lock` for PDF/image support and Tesseract plus the desired language packs for OCR. Configure file limits, chunking, OCR and customer uploads in deployment.yaml. Use the same `--workspace` for subsequent runs or the HTTP service. Exports do not contain your database or memory records.\n",
            "DEPENDENCIES.md": "# Dependencies\n\nPydantic (MIT), jsonschema (MIT), PyYAML (MIT), HTTPX (BSD-3-Clause), Hatchling build tooling (MIT). The lock records exact versions. Dependencies are installed separately with their original license metadata.\n",
        }
        operations = {binding.get("operation") for binding in bindings.values() if binding["kind"] == "artifact"}
        if "office" in operations:
            files["requirements.lock"] += "\nxlsxwriter==3.2.5\npython-docx==1.2.0\npython-pptx==1.0.2\nlxml==5.3.0\nPillow==12.0.0\n"
        elif "comic" in operations:
            files["requirements.lock"] += "\nPillow==12.0.0\n"
        if "spice" in operations:
            files["README.md"] += "\nCircuit tools require ngspice on PATH, or EVOSPRIG_NGSPICE pointing to its executable.\n"
        if any(binding["kind"] == "mcp" for binding in bindings.values()):
            files["requirements.lock"] += (Path(__file__).parent / "mcp.lock").read_text()
        files["requirements-documents.lock"] = "pypdfium2==4.30.0\nPillow==12.0.0\n"
        if target != "python":
            files["requirements.lock"] += (Path(__file__).parent / "server.lock").read_text()
            files["serve.py"] = SERVICE
            files["README.md"] += SERVICE_README
        if target == "container":
            files["Dockerfile"] = DOCKERFILE
            files[".dockerignore"] = (
                "**\n!src/**\n!agent.yaml\n!agent.lock.json\n!tool-bindings.json\n!memory-config.json\n!serve.py\n!requirements.lock\n!pyproject.toml\n!LICENSE\n!NOTICE\n"
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

The operator can start this service with `models: {}` in its deployment file, then
add model connections when the inference servers are ready. New runs read the updated
profile; existing runs retain their original connections. `GET /model-contract`
returns the required roles and capabilities. End-user clients only send task input.

Send `Authorization: Bearer <token>` to `POST /runs` with `{"input": {...}}`.
Poll `GET /runs/{run_id}`, read `/runs/{run_id}/events` (SSE, Last-Event-ID),
submit `POST /runs/{run_id}/input` with `{"path": "...", "response": {...}}`, or
`POST /runs/{run_id}/cancel`. Restarting the service resumes queued/checkpointed runs.
This is a single-agent, single-trust-domain service. Use a separate workspace per
exported version. Put TLS at a reverse proxy for remote access; browser origins are
rejected. `/health` is public and contains no run data.

## Customer knowledge library

Enable `documents.customer_uploads: true` in deployment.yaml to let your application
manage its knowledge library. Authenticate with the service token from your backend.
Upload raw file bytes to `POST /documents/upload?filename=manual.pdf`, poll the returned
job at `GET /documents/jobs/{id}`, list `GET /documents`, search
`GET /documents/search?query=...`, or delete `DELETE /documents/{id}`.
Uploading the same source replaces it atomically after successful parsing.
The deployed graph stays unchanged and the next run uses the updated library.
Keep service credentials in your application backend; do not embed them in browser code.

## Container target

When a Dockerfile is present: `docker build -t my-agent .`, then
`docker run --rm -p 127.0.0.1:8080:8080 -e EVOSPRIG_SERVICE_TOKEN -e MODEL_API_KEY
-v evosprig-state:/state my-agent --host 0.0.0.0 --workspace /state --mock`.
For live calls, mount your deployment file with `-v /path/to/deployment.yaml:/app/deployment.yaml:ro` and replace `--mock` with `--profile /app/deployment.yaml`. The image runs as UID 10001. Credentials, runtime
history and model weights are not build inputs. The Python base image is tag-pinned;
pin its digest in your deployment registry for immutable rebuilds.
"""

DOCKERFILE = """FROM python:3.12.12-slim
WORKDIR /app
ARG DOCUMENT_PARSERS=0
ARG OCR_LANGUAGES="eng chi-sim"
COPY requirements.lock requirements-documents.lock pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.lock
RUN if [ "$DOCUMENT_PARSERS" = "1" ]; then \
    python -m pip install --no-cache-dir -r requirements-documents.lock && \
    apt-get update && apt-get install -y --no-install-recommends tesseract-ocr $(for lang in $OCR_LANGUAGES; do echo tesseract-ocr-$lang; done) && \
    rm -rf /var/lib/apt/lists/*; fi
COPY . .
RUN python -m pip install --no-cache-dir --no-deps . && mkdir /state && chown 10001:10001 /state
USER 10001:10001
EXPOSE 8080
VOLUME ["/state"]
ENTRYPOINT ["python", "serve.py"]
CMD ["--host", "0.0.0.0", "--workspace", "/state"]
"""
