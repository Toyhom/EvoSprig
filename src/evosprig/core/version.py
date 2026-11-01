"""Resolve declared text resources and freeze a content-addressed version."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from evosprig import __version__

from .spec import AgentSpec, canonical_json, digest

SECRET = re.compile(
    r"\bsk-[A-Za-z0-9_-]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I
)


def check_public_text(text: str) -> None:
    if SECRET.search(text):
        raise ValueError("credential-like content found; use an environment variable binding")


def resource_path(root: Path, path: str) -> Path:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in path or not relative.parts:
        raise ValueError("resource path must be relative and contained in the project")
    if any(
        part.startswith(".") or part in ("project-private", "local-data") for part in relative.parts
    ):
        raise ValueError("private resource path is not allowed")
    root = root.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("resource symlink escapes project")
    return target


@dataclass(frozen=True)
class AgentVersion:
    version_id: str
    spec_json: str
    resources_json: str
    lock_json: str

    @property
    def spec(self) -> AgentSpec:
        return AgentSpec.model_validate_json(self.spec_json)

    @property
    def resources(self) -> dict[str, str]:
        return json.loads(self.resources_json)

    @property
    def lock(self) -> dict:
        return json.loads(self.lock_json)


def compile_agent(spec: AgentSpec, root: str | Path = ".") -> AgentVersion:
    spec = AgentSpec.model_validate_json(spec.canonical())
    check_public_text(spec.canonical())
    resources, hashes = {}, {}
    for name, resource in spec.resources.items():
        path = resource_path(Path(root), resource.path)
        if not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError(f"resource {name} must be a text file of at most 1 MB")
        content = path.read_bytes()
        text = content.decode("utf-8")
        check_public_text(text)
        resources[name] = text
        hashes[name] = hashlib.sha256(content).hexdigest()
    lock = {
        "format_version": "0.1",
        "runtime": __version__,
        "spec_hash": spec.spec_hash,
        "resources": hashes,
        "plugins": {name: value.model_dump() for name, value in spec.tools.items()},
    }
    version_id = digest(lock)
    lock["agent_version"] = version_id
    return AgentVersion(
        version_id, spec.canonical(), canonical_json(resources), canonical_json(lock)
    )
