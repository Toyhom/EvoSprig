from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from evosprig.config import make_models
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import SECRET, compile_agent
from evosprig.plugins.builtin_tools import builtin_registry


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
        if name == "export":
            sub.add_argument("--out", required=True, type=Path)
            sub.add_argument("--target", default="python")
    serve = commands.add_parser("serve")
    serve.add_argument("--workspace", type=Path, default=Path(".evosprig"))
    serve.add_argument("--project", type=Path)
    serve.add_argument("--studio-dir", type=Path)
    serve.add_argument("--profile", type=Path)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--token-env", help="Optional API bearer-token environment variable")
    args = parser.parse_args()
    try:
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
                    store.create(spec)
            token = os.environ.get(args.token_env) if args.token_env else None
            if args.token_env and not token:
                raise ValueError("API token environment variable is empty")
            uvicorn.run(
                create_app(
                    args.workspace, profile=args.profile, studio_dir=args.studio_dir, token=token
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
                Runtime(make_models(spec, args.profile, args.mock), builtin_registry()).run(
                    version, json.loads(args.input)
                )
            )
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
            if result.status != "succeeded":
                raise SystemExit(1)
        elif args.command == "export":
            from evosprig.exporters.python import export_python

            print(json.dumps(export_python(version, args.out, target=args.target), indent=2))
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
    except ValueError as exc:
        print(SECRET.sub("[redacted]", str(exc))[:2000], file=sys.stderr)
        raise SystemExit(2) from None
    except (OSError, ImportError) as exc:
        # Keep potentially sensitive input values out of command error output.
        print(
            f"{type(exc).__name__}: command failed; check project schema, dependencies and paths",
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
