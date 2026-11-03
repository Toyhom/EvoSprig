"""Private stdio protocol used by the media service's model process."""

import contextlib
import json
import os
import sys


def main():
    config = json.loads(sys.stdin.readline())["config"]
    with contextlib.redirect_stdout(sys.stderr):
        if os.environ.get("EVOSPRIG_MEDIA_ATTENTION") == "sdpa":
            import diffusers.utils.import_utils as availability

            availability._xformers_available = False
            availability._flash_attn_available = False
            availability._flash_attn_3_available = False
        from backend import MediaBackend

        backend = MediaBackend(**config)
    for line in sys.stdin:
        try:
            task = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                output = backend.execute(
                    task["operation"], task["payload"], task["name"], lambda: False
                )
            reply = {"output": output}
        except Exception as exc:
            reply = {"error": f"{type(exc).__name__}: {str(exc)[:500]}"}
        print(json.dumps(reply), flush=True)


if __name__ == "__main__":
    main()
