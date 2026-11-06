"""Desktop process ownership and lock contention use the OS's native primitives."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from evosprig.process_support import (
    detached_process_options,
    file_lock,
    process_identity,
    terminate_process_tree,
)


def test_lock_is_exclusive_across_processes_and_released(tmp_path):
    path = tmp_path / "operation.lock"
    code = (
        "from evosprig.process_support import file_lock; import sys\n"
        "with file_lock(sys.argv[1], .15): print('acquired')\n"
    )
    with file_lock(path):
        result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True)
        assert result.returncode != 0
        assert b"TimeoutError" in result.stderr
    result = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True)
    assert result.returncode == 0
    assert b"acquired" in result.stdout


def test_process_identity_and_owned_termination():
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], **detached_process_options()
    )
    try:
        birth = process_identity(child.pid)
        assert birth and birth == process_identity(child.pid)
        terminate_process_tree(child.pid)
        child.wait(timeout=5)
        assert process_identity(child.pid) is None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_service_never_owns_an_unverified_pid(tmp_path, monkeypatch):
    from evosprig import local_services

    profile = tmp_path / "deployment.yaml"
    profile.write_text("models: {}\nservices:\n  test:\n    health_url: http://127.0.0.1:1/health\n")
    manager = local_services.ServiceManager(profile)
    manager._write("test", {"pid": os.getpid(), "birth": None})
    monkeypatch.setattr(local_services, "_identity", lambda _: None)
    monkeypatch.setattr(manager, "_health", lambda _: None)
    monkeypatch.setattr(local_services, "terminate_process_tree", lambda *_: pytest.fail("unowned PID"))
    assert not manager.status("test")["managed"]
    assert not manager.stop("test")["stopped"]
    assert Path(profile).exists()
