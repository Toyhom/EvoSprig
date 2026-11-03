"""One model family per child process, retaining warm models between jobs."""

import json
import select
import subprocess
import sys
import threading
from pathlib import Path

from backend import MediaBackend


class IsolatedMediaBackend(MediaBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.child = None
        self.family = None
        self.worker_script = Path(__file__).with_name("model_worker.py")
        self.stopping = threading.Event()

    def shutdown(self):
        """Signal the execution thread; that thread owns process/pipe cleanup."""
        self.stopping.set()

    def close(self):
        child, self.child = self.child, None
        self.family = self.loaded = None
        if child is None:
            return
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
        child.stdin.close()
        child.stdout.close()

    def execute(self, operation, payload, name, canceled):
        request_canceled = canceled
        def canceled():
            return self.stopping.is_set() or request_canceled()
        if canceled():
            raise RuntimeError("job canceled")
        if operation == "compose":
            return super().execute(operation, payload, name, canceled)
        family = "video" if operation in {"video", "generate-video"} else "image"
        if canceled():
            raise RuntimeError("job canceled")
        if self.child is None or self.child.poll() is not None or self.family != family:
            self.close()
            self.child = subprocess.Popen(
                [sys.executable, "-u", str(self.worker_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )
            config = dict(
                root=str(self.root),
                image_model=self.image_model,
                video_model=self.video_model,
                base_url=self.base_url,
                seed=self.seed,
                image_steps=self.image_steps,
                video_steps=self.video_steps,
                width=self.width,
                height=self.height,
            )
            self.child.stdin.write(json.dumps({"config": config}) + "\n")
            self.family = family
        child = self.child
        child.stdin.write(
            json.dumps({"operation": operation, "payload": payload, "name": name}) + "\n"
        )
        child.stdin.flush()
        while True:
            if canceled():
                self.close()
                raise RuntimeError("job canceled")
            ready, _, _ = select.select([child.stdout], [], [], 0.25)
            if ready:
                line = child.stdout.readline()
                if not line:
                    self.close()
                    raise RuntimeError("model worker exited before returning the asset")
                try:
                    reply = json.loads(line)
                    if not isinstance(reply, dict) or not ({"output", "error"} & reply.keys()):
                        raise ValueError("missing response fields")
                except ValueError:
                    self.close()
                    raise RuntimeError("model worker returned an invalid response") from None
                if "error" in reply:
                    self.close()
                    raise RuntimeError(reply["error"])
                self.loaded = family
                return reply["output"]
            if child.poll() is not None:
                self.close()
                raise RuntimeError("model worker exited before returning the asset")
