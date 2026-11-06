"""Native file locks and process ownership for desktop and server deployments."""

import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(path, timeout=None):
    with Path(path).open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()

            def acquire():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def acquire():
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(handle, fcntl.LOCK_UN)
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                import errno

                if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                    raise
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("another operation holds the file lock") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            release()


def process_identity(pid):
    """Preserve Linux receipts; use native process creation time on macOS/Windows."""
    if sys.platform.startswith("linux"):
        try:
            rest = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            return None if rest[0] == "Z" else rest[19]
        except (OSError, IndexError):
            return None
    import psutil

    try:
        process = psutil.Process(pid)
        return None if process.status() == psutil.STATUS_ZOMBIE else str(process.create_time())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def detached_process_options():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def terminate_process_tree(pid, *, force=False):
    if os.name != "nt":
        os.killpg(pid, signal.SIGKILL if force else signal.SIGTERM)
        return
    import psutil

    try:
        parent = psutil.Process(pid)
        processes = parent.children(recursive=True) + [parent]
        for process in processes:
            try:
                process.kill() if force else process.terminate()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass
