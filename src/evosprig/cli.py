from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from jsonschema.exceptions import ValidationError as JSONValidationError
from pydantic import ValidationError

from evosprig.config import load_principals, make_models, make_tools, restore_models
from evosprig.core.journal import Scope
from evosprig.core.protocols import ExecutionError
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import SECRET, compile_agent
from evosprig.plugins.sqlite_journal import SQLiteJournal


def main():
    parser = argparse.ArgumentParser(prog="evosprig")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run", "export"):
        sub = commands.add_parser(name)
        sub.add_argument("spec", type=Path)
        if name == "run":
            sub.add_argument("--input", required=True, help="JSON input")
            sub.add_argument("--mock", action="store_true")
            sub.add_argument("--profile", type=Path)
            sub.add_argument("--workspace", type=Path, default=Path(".evosprig"))
            sub.add_argument("--run-id")
            sub.add_argument("--allow-writes", action="store_true")
        if name == "export":
            sub.add_argument("--profile", type=Path)
            sub.add_argument("--out", required=True, type=Path)
            sub.add_argument("--target", default="python")
    for name in ("runs", "inspect", "resume", "cancel"):
        sub = commands.add_parser(name)
        sub.add_argument("--workspace", type=Path, default=Path(".evosprig"))
        if name != "runs":
            sub.add_argument("run_id")
        if name == "resume":
            sub.add_argument("--path", help="Waiting node or operation path")
            sub.add_argument("--response", help="JSON human input or reconciled tool result")
    imported = commands.add_parser("import")
    imported.add_argument("archive", type=Path)
    imported.add_argument("--out", type=Path, help="Save validated declarative project data")
    serve = commands.add_parser("serve")
    serve.add_argument("--workspace", type=Path, default=Path(".evosprig"))
    serve.add_argument("--project", type=Path)
    serve.add_argument("--studio-dir", type=Path)
    serve.add_argument("--profile", type=Path)
    serve.add_argument("--port", type=int, default=18766)
    serve.add_argument(
        "--auth-file", type=Path, help="YAML principal and token environment references"
    )
    serve.add_argument("--token-env", help="Optional API bearer-token environment variable")
    serve.add_argument("--max-concurrent-runs", type=int, default=4)
    from evosprig.evolution.cli import add_commands, run_command

    add_commands(commands)
    args = parser.parse_args()
    try:
        if args.command == "import":
            from evosprig.core.spec import save_spec
            from evosprig.exporters.importer import inspect_archive

            version, report = inspect_archive(args.archive.read_bytes())
            if args.out:
                args.out.mkdir(parents=True, exist_ok=False)
                save_spec(version.spec, args.out / "agent.yaml")
                for key, resource in version.spec.resources.items():
                    path = args.out / resource.path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(version.resources[key])
            print(json.dumps(report, indent=2))
            return
        if args.command in {
            "evaluate",
            "improve",
            "studies",
            "versions",
            "release",
            "rollback",
            "export-version",
        }:
            run_command(args)
            return
        if args.command in {"runs", "inspect", "resume", "cancel"}:
            journal = SQLiteJournal(args.workspace / "runs.sqlite")
            if args.command == "runs":
                records = [
                    {
                        "run_id": record["run_id"],
                        "scope": record["scope"],
                        "status": record["status"],
                    }
                    for record in journal.list()
                ]
                print(json.dumps(records, indent=2))
                return
            record = journal.get(args.run_id)
            runtime = Runtime(
                restore_models(record["metadata"]["models"]),
                make_tools(
                    args.workspace,
                    Scope(**record["scope"]),
                    bindings=record["metadata"].get("tools", {}),
                ),
                journal=journal,
                allow_writes=record["metadata"]["allow_writes"],
            )
            if args.command == "resume":
                if bool(args.path) != bool(args.response):
                    raise ValueError("--path and --response must be supplied together")
                if args.response:
                    journal.respond(args.run_id, args.path, json.loads(args.response))
                result = asyncio.run(runtime.resume(args.run_id))
            elif args.command == "cancel":
                result = asyncio.run(runtime.cancel_run(args.run_id))
            else:
                result = runtime.get(args.run_id)
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            if result.status in {"failed", "canceled"}:
                raise SystemExit(1)
            return
        if args.command == "serve":
            import uvicorn

            from evosprig.plugins.sqlite_projects import ProjectStore
            from evosprig.server.app import create_app

            if args.project:
                spec = load_spec(args.project)
                version = compile_agent(spec, args.project.parent)
                store = ProjectStore(args.workspace / "projects.sqlite")
                if not any(item["id"] == spec.id for item in store.list()):
                    root = args.workspace / "projects" / spec.id
                    for key, resource in spec.resources.items():
                        path = root / resource.path
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(version.resources[key])
                    store.create(spec, resources=version.resources)
            token = os.environ.get(args.token_env) if args.token_env else None
            if args.token_env and not token:
                raise ValueError("API token environment variable is empty")
            uvicorn.run(
                create_app(
                    args.workspace,
                    profile=args.profile,
                    studio_dir=args.studio_dir,
                    token=token,
                    principals=load_principals(args.auth_file) if args.auth_file else None,
                    max_concurrent_runs=args.max_concurrent_runs,
                ),
                host="127.0.0.1",
                port=args.port,
                access_log=False,
            )
            return
        spec = load_spec(args.spec)
        version = compile_agent(spec, args.spec.parent)
        if args.command == "validate":
            print(json.dumps(version.lock, indent=2))
        elif args.command == "run":
            result = asyncio.run(
                Runtime(
                    make_models(spec, args.profile, args.mock),
                    make_tools(args.workspace, Scope(spec.id), profile=args.profile),
                    journal=SQLiteJournal(args.workspace / "runs.sqlite"),
                    allow_writes=args.allow_writes,
                ).run(version, json.loads(args.input), run_id=args.run_id)
            )
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            if result.status in {"failed", "canceled"}:
                raise SystemExit(1)
        elif args.command == "export":
            from evosprig.exporters.python import export_python

            bindings = {}
            if args.profile:
                import yaml

                bindings = yaml.safe_load(args.profile.read_text()).get("tools", {})
            print(
                json.dumps(
                    export_python(version, args.out, target=args.target, tool_bindings=bindings),
                    indent=2,
                )
            )
    except JSONValidationError as exc:
        print(
            json.dumps({"validation_error": {"location": list(exc.path), "rule": exc.validator}}),
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    except ValidationError as exc:
        issues = [
            {
                "location": list(error["loc"]),
                "message": SECRET.sub("[redacted]", error["msg"])[:500],
            }
            for error in exc.errors()
        ]
        print(json.dumps({"validation_errors": issues}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from None
    except (ValueError, ExecutionError) as exc:
        print(SECRET.sub("[redacted]", str(exc))[:2000], file=sys.stderr)
        raise SystemExit(2) from None
    except (OSError, ImportError, KeyError) as exc:
        # Keep potentially sensitive input values out of command error output.
        print(
            f"{type(exc).__name__}: command failed; check project schema, dependencies and paths",
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
