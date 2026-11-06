"""Loopback-only desktop backend, owned by the desktop parent's input pipe."""

import argparse
import asyncio
import json
import multiprocessing
import os
import socket
import sys
import threading
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--studio", required=True, type=Path)
    args = parser.parse_args()
    # Credentials travel over a private pipe, never through process arguments or URLs.
    startup = json.loads(sys.stdin.readline())
    token = startup["token"]
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("desktop authentication token is missing")
    for name, value in startup.get("credentials", {}).items():
        os.environ[name] = value
    args.workspace.mkdir(parents=True, exist_ok=True)
    profile = args.workspace / "deployment.yaml"
    if not profile.exists():
        profile.write_text("models: {}\ntools: {}\nservices: {}\n", encoding="utf-8")
    import uvicorn

    from evosprig.server.app import create_app

    app = create_app(args.workspace, profile=profile, studio_dir=args.studio, token=token)
    # Hold the ephemeral socket throughout startup: no free-port probing race.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning"))
    stopped = threading.Event()

    def parent_pipe():
        for _ in sys.stdin:
            pass
        stopped.set()

    threading.Thread(target=parent_pipe, daemon=True).start()

    async def serve():
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            while not task.done() and not stopped.is_set():
                if server.started:
                    print(json.dumps({"port": sock.getsockname()[1]}), flush=True)
                    break
                await asyncio.sleep(0.05)
            while not task.done() and not stopped.is_set():
                await asyncio.sleep(0.1)
        finally:
            server.should_exit = True
            await task
            sock.close()

    asyncio.run(serve())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
