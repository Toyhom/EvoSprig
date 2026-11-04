"""Deployment-owned, persistent local services, independent of agent run lifetimes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from pydantic import Field, model_validator

from evosprig.core.spec import Contract


class ServiceConfig(Contract):
    health_url: str
    command: list[str] = Field(default_factory=list)
    cwd: str = "."
    warmup_url: str | None = None
    warmup_body: dict = Field(default_factory=dict)
    ready: dict = Field(default_factory=dict)
    timeout_seconds: float = Field(default=1800, gt=0, le=7200)
    poll_seconds: float = Field(default=2, gt=0, le=60)
    # A ready response is authoritative. Otherwise warm once per service generation.
    auth_env: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    autostart: bool = True
    retention: Literal["persistent"] = "persistent"
    gpu_devices: list[Annotated[int, Field(ge=0)]] | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def local_only(self):
        if self.gpu_devices is not None and len(set(self.gpu_devices)) != len(self.gpu_devices):
            raise ValueError("GPU positions must be unique")
        for endpoint in (self.health_url, self.warmup_url):
            if endpoint:
                url = urlsplit(endpoint)
                if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"}
                        or url.username or url.password or url.query or url.fragment):
                    raise ValueError("local services require credential-free loopback HTTP URLs")
        if self.warmup_url and not self.ready:
            raise ValueError("warmup services require a ready predicate in their health response")
        if any(not value or "\x00" in value for value in self.command):
            raise ValueError("service command arguments must be nonempty")
        return self


def service_environment(config, inherited=None):
    """Select positions inside an existing allocation, or physical IDs outside one."""
    env = dict(os.environ if inherited is None else inherited)
    if config.gpu_devices is not None:
        visible = env.get("CUDA_VISIBLE_DEVICES")
        if visible is None:
            selected = [str(index) for index in config.gpu_devices]
        else:
            available = [part.strip() for part in visible.split(",") if part.strip() and part.strip() != "-1"]
            if any(index >= len(available) for index in config.gpu_devices):
                raise ValueError("gpu_devices selects a position outside CUDA_VISIBLE_DEVICES")
            selected = [available[index] for index in config.gpu_devices]
        env["CUDA_VISIBLE_DEVICES"] = ",".join(selected)
    return env


def _identity(pid):
    """Linux process birth time guards against killing a recycled PID."""
    try:
        rest = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if rest[0] == "Z" else rest[19]
    except (OSError, IndexError):
        return None


def _request(url, body=None, timeout=5, auth_env=None):
    headers = {"Content-Type": "application/json"}
    if body is not None:
        headers["Idempotency-Key"] = "preload-" + uuid.uuid4().hex
    if auth_env:
        if not os.environ.get(auth_env):
            raise ValueError("Local service authentication variable is missing: " + auth_env)
        headers["Authorization"] = "Bearer " + os.environ[auth_env]
    request = Request(url, data=None if body is None else json.dumps(body).encode(),
                      headers=headers)
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("service response exceeds 1 MB")
        return json.loads(raw)


class ServiceManager:
    def __init__(self, profile, state_dir=None):
        from evosprig.config import read_profile

        self.profile = Path(profile).resolve()
        self.configs = {name: ServiceConfig.model_validate(value)
                        for name, value in read_profile(profile).get("services", {}).items()}
        if any(not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", name) for name in self.configs):
            raise ValueError("service names must contain letters, digits, underscores or hyphens")
        self.root = Path(state_dir) if state_dir else self.profile.parent / ".evosprig-services"
        self.root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _lock(self, name):
        import fcntl

        with (self.root / f"{name}.lock").open("a") as lock:
            deadline = time.monotonic() + self.configs[name].timeout_seconds + 10
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"{name}: another service operation is still active") from None
                    time.sleep(0.05)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _read(self, name):
        try:
            return json.loads((self.root / f"{name}.json").read_text())
        except FileNotFoundError:
            return {}

    def _write(self, name, state):
        target = self.root / f"{name}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(target)

    @staticmethod
    def _health(config):
        try:
            value = _request(config.health_url, auth_env=config.auth_env)
            return value if isinstance(value, dict) else None
        except (OSError, URLError, ValueError):
            return None

    def status(self, name):
        config = self.configs[name]
        state = self._read(name)
        health = self._health(config)
        owned = bool(state.get("pid") and _identity(state["pid"]) == state.get("birth"))
        ready = health is not None and all(health.get(k) == v for k, v in config.ready.items())
        if config.warmup_url and not config.ready:
            ready = ready and bool(state.get("warmed"))
        return {"name": name, "ready": ready, "reachable": health is not None,
                "managed": owned, "pid": state.get("pid") if owned else None,
                "retention": config.retention, "health": health,
                "gpu_devices": config.gpu_devices,
                "cuda_visible_devices": state.get("cuda_visible_devices") if owned else None}

    def ensure(self, name):
        config = self.configs[name]
        if config.auth_env and not os.environ.get(config.auth_env):
            raise ValueError("Local service authentication variable is missing: " + config.auth_env)
        fields = config.model_dump(mode="json", exclude={"gpu_devices"} if config.gpu_devices is None else set())
        signature = hashlib.sha256(json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        with self._lock(name):
            state = self._read(name)
            health = self._health(config)
            owned = bool(state.get("pid") and _identity(state["pid"]) == state.get("birth"))
            if owned and state.get("signature") != signature:
                raise ValueError(f"{name}: configuration changed; explicitly stop the old service first")
            if health is None and not owned:
                if not config.command:
                    raise ValueError(f"{name}: service is unavailable; start its server first")
                cwd = (self.profile.parent / config.cwd).resolve()
                env = service_environment(config)
                with (self.root / f"{name}.log").open("ab") as log:
                    child = subprocess.Popen(config.command, cwd=cwd, stdin=subprocess.DEVNULL,
                                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
                state = {"pid": child.pid, "birth": _identity(child.pid),
                         "signature": signature, "warmed": False, "started": time.time(),
                         "cuda_visible_devices": env.get("CUDA_VISIBLE_DEVICES")}
                self._write(name, state)
                owned = True
            elif not owned:
                # An existing endpoint belongs to its operator, even if the profile has a command.
                state = {"signature": signature, "warmed": False, "external": True}
            deadline = time.monotonic() + config.timeout_seconds
            while health is None:
                if owned and _identity(state["pid"]) != state.get("birth"):
                    raise RuntimeError(f"{name}: process exited; inspect {self.root / (name + '.log')}")
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"{name}: startup timed out; service retained for inspection")
                time.sleep(config.poll_seconds)
                health = self._health(config)
            already_ready = bool(config.ready) and all(health.get(k) == v for k, v in config.ready.items())
            if config.warmup_url and not already_ready:
                _request(config.warmup_url, config.warmup_body,
                         timeout=max(1, deadline - time.monotonic()), auth_env=config.auth_env)
                state["warmed"] = True
            while True:
                health = self._health(config)
                if health is not None and all(health.get(k) == v for k, v in config.ready.items()):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"{name}: warmup readiness timed out")
                time.sleep(config.poll_seconds)
            state["warmed"] = True
            self._write(name, state)
            return self.status(name)

    def stop(self, name):
        if name not in self.configs:
            raise KeyError(name)
        with self._lock(name):
            state = self._read(name)
            pid = state.get("pid")
            if not pid or _identity(pid) != state.get("birth"):
                return {"name": name, "stopped": False, "reason": "not a managed live process"}
            os.killpg(pid, signal.SIGTERM)
            deadline = time.monotonic() + 10
            while _identity(pid) == state["birth"] and time.monotonic() < deadline:
                time.sleep(0.1)
            if _identity(pid) == state["birth"]:
                os.killpg(pid, signal.SIGKILL)
            self._write(name, {"stopped": time.time()})
            return {"name": name, "stopped": True}


def prepare_services(profile):
    if not profile:
        return []
    manager = ServiceManager(profile)
    return [manager.ensure(name) for name, config in manager.configs.items() if config.autostart]


def add_commands(commands):
    parser = commands.add_parser("services", help="Preload and retain deployment model/tool servers")
    parser.add_argument("action", choices=["start", "status", "stop"])
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--name")


def run_command(args):
    manager = ServiceManager(args.profile)
    operation = {"start": manager.ensure, "status": manager.status, "stop": manager.stop}[args.action]
    print(json.dumps([operation(name) for name in ([args.name] if args.name else manager.configs)], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_commands(parser.add_subparsers(dest="command", required=True))
    run_command(parser.parse_args())
