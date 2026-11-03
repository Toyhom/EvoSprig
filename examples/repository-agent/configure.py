"""Bind the maintenance team to a local repository and its named test command."""

import argparse
from pathlib import Path

import yaml


def profile(*, command, editable_paths, model_url="http://127.0.0.1:8000/v1", model_name="local-model"):
    return {
        "models": {"main": {"base_url": model_url, "model": model_name, "api_key_env": "MODEL_API_KEY",
                            "capabilities": ["text", "structured_output", "tool_calling"],
                            "json_mode": "without_tools"}},
        "tools": {"repository." + operation: {
            "kind": "repository", "name": "repository." + operation, "operation": operation,
            "repository_env": "AGENT_REPOSITORY", "editable_paths": editable_paths,
            "checks": {"unit": command}, "timeout_seconds": 120,
        } for operation in ["open", "list", "read", "write", "diff", "check"]},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("deployment.yaml"))
    parser.add_argument("--editable", action="append", default=[])
    parser.add_argument("--model-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="local-model")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Supply a test command after --")
    args.out.write_text(yaml.safe_dump(profile(command=command, editable_paths=args.editable,
        model_url=args.model_url, model_name=args.model), sort_keys=False))
