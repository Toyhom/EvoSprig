"""Run in separate CLI processes to prove persisted human/job recovery.

Default replays the checked-in storyboard; --live requests one real model response.
"""

import argparse
import getpass
import hashlib
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml
from build_agent import ARTIFACT, STORY, spec

from evosprig.core.spec import save_spec
from evosprig.core.version import compile_agent
from evosprig.exporters.python import export_python
from evosprig.server.canvas import to_canvas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--approve-demo-storyboard", action="store_true")
    args = parser.parse_args()
    if not args.approve_demo_storyboard:
        parser.error(
            "this automated demonstration requires --approve-demo-storyboard; use Studio for manual review"
        )
    root = Path(__file__).resolve().parent
    args.workspace.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ)
    if args.live and not environment.get("DEEPSEEK_API_KEY"):
        environment["DEEPSEEK_API_KEY"] = getpass.getpass("DeepSeek test key (hidden): ")
    token = secrets.token_urlsafe(32)
    environment["EVOSPRIG_RENDER_TOKEN"] = token
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    connection = {
        "kind": "external_http",
        "name": "media.render",
        "description": "Render the approved three-shot original motion graphic",
        "endpoint": f"http://127.0.0.1:{port}/jobs",
        "auth_env": "EVOSPRIG_RENDER_TOKEN",
        "input_schema": {
            "type": "object",
            "properties": {"storyboard": STORY},
            "required": ["storyboard"],
            "additionalProperties": False,
        },
        "output_schema": ARTIFACT,
        "job_timeout_seconds": 300.0,
    }
    profile = args.workspace / "deployment.yaml"
    profile.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "main": {
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-flash",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "options": {"thinking": {"type": "disabled"}},
                    }
                },
                "tools": {"media.render": connection},
            }
        )
    )
    chosen = spec.model_copy(deep=True)
    if not args.live:
        from evosprig.core.spec import Node

        story = json.loads((root / "results/storyboard.json").read_text())
        chosen.graph.nodes["storyboard"] = Node(
            type="transform",
            inputs={key: {"value": value} for key, value in story.items()},
            output_schema=STORY,
        )
        chosen.models = {}
    project = args.workspace / "project"
    project.mkdir()
    save_spec(chosen, project / "agent.yaml")
    (project / "prompts").mkdir()
    (project / "prompts/director.md").write_text((root / "prompts/director.md").read_text())
    (args.workspace / "canvas.json").write_text(json.dumps(to_canvas(chosen, {}), indent=2))
    server_env = {key: value for key, value in environment.items() if key != "DEEPSEEK_API_KEY"}
    server = None

    def cli(*parts):
        result = subprocess.run(
            [sys.executable, "-m", "evosprig", *map(str, parts)],
            env=environment,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(
                "workflow process failed: " + result.stderr[:500] + result.stdout[-500:]
            )
        return json.loads(result.stdout)

    try:
        with (args.workspace / "renderer.log").open("w") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    str(root / "renderer_service.py"),
                    "--state",
                    str(args.workspace / "renderer"),
                    "--artifacts",
                    str(args.artifacts),
                    "--port",
                    str(port),
                ],
                env=server_env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            with httpx.Client(trust_env=False, timeout=2) as client:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("renderer failed before readiness")
                    try:
                        if client.get(f"http://127.0.0.1:{port}/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
                else:
                    raise RuntimeError("renderer readiness timed out")
            first = cli(
                "run",
                project / "agent.yaml",
                "--profile",
                profile,
                "--workspace",
                args.workspace,
                "--allow-writes",
                "--input",
                json.dumps(
                    {
                        "brief": "A tiny seed finds its own patient rhythm, reaches daylight, and blooms under the stars."
                    }
                ),
            )
            assert first["status"] == "waiting_input", first.get("error")
            run_id = first["run_id"]
            story = first["waiting"][0]["input"]["storyboard"]
            (args.workspace / "storyboard.json").write_text(json.dumps(story, indent=2) + "\n")
            print(
                "Storyboard saved; scripted demonstration approves its schema-valid content.",
                flush=True,
            )
            second = cli(
                "resume",
                run_id,
                "--workspace",
                args.workspace,
                "--path",
                first["waiting"][0]["path"],
                "--response",
                json.dumps(story),
            )
            assert second["status"] == "waiting_external", second.get("error")
            job_id = second["waiting"][0]["job_id"]
            print(
                "External job persisted; the CLI process has exited. Resuming from a new process.",
                flush=True,
            )
            deadline = time.monotonic() + 300
            result = second
            while result["status"] == "waiting_external" and time.monotonic() < deadline:
                time.sleep(1)
                result = cli("resume", run_id, "--workspace", args.workspace)
            assert result["status"] == "succeeded", result.get("error")
            assert result["output"]["job_id"] == job_id
            assert (
                hashlib.sha256(Path(result["output"]["path"]).read_bytes()).hexdigest()
                == result["output"]["sha256"]
            )
            with sqlite3.connect(args.workspace / "renderer/jobs.sqlite") as db:
                count, attempts = db.execute("SELECT COUNT(*), SUM(attempts) FROM jobs").fetchone()
            assert count == attempts == 1, (count, attempts)
            version = compile_agent(chosen, project)
            exported = export_python(
                version,
                args.workspace / "export",
                target="http",
                tool_bindings={"media.render": connection},
            )
            report = {
                "model": "deepseek-flash" if args.live else "replay/no-model",
                "runtime_status": result["status"],
                "agent_version": version.version_id,
                "usage": result["usage"],
                "artifact": result["output"],
                "renderer_jobs": count,
                "render_attempts": attempts,
                "restarted_after_submission": True,
                "review": "scripted demo approval",
                "export": exported,
                "rendering": "CPU procedural Pillow + FFmpeg, no neural video generation, no audio",
            }
            (args.workspace / "result.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2), flush=True)
    finally:
        environment.pop("DEEPSEEK_API_KEY", None)
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=45)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
