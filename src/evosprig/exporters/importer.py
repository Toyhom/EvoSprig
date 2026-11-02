"""Inspect declarative export data without extracting or executing archived code."""

import hashlib
import io
import json
import stat
import zipfile
from pathlib import PurePosixPath

import yaml

from evosprig.core.spec import AgentSpec
from evosprig.core.version import compile_snapshot
from evosprig.exporters.python import compatibility_report

MAX_BYTES = 20_000_000


def inspect_archive(data: bytes):
    if len(data) > MAX_BYTES:
        raise ValueError("archive exceeds 20 MB")
    files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 500 or sum(item.file_size for item in infos) > MAX_BYTES:
                raise ValueError("archive expands beyond limits")
            for item in infos:
                name = item.filename
                path = PurePosixPath(name)
                if (
                    name in files
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in name
                    or str(path) != name
                    or item.is_dir()
                    or stat.S_ISLNK(item.external_attr >> 16)
                ):
                    raise ValueError("unsafe or duplicated archive path")
                files[name] = archive.read(item)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
        raise ValueError("invalid export archive") from None
    try:
        manifest = json.loads(files["manifest.json"])
        if not isinstance(manifest, dict) or set(manifest) != set(files) - {"manifest.json"}:
            raise ValueError("manifest file list mismatch")
        for name, checksum in manifest.items():
            if hashlib.sha256(files[name]).hexdigest() != checksum:
                raise ValueError("export file checksum mismatch")
        spec = AgentSpec.model_validate(yaml.safe_load(files["agent.yaml"]))
        reserved = {
            "agent.yaml",
            "agent.lock.json",
            "manifest.json",
            "tool-bindings.json",
            "app.py",
            "serve.py",
            "build_agent.py",
            "pyproject.toml",
            "requirements.lock",
            "README.md",
            "LICENSE",
            "NOTICE",
            "Dockerfile",
            "export-report.json",
        }
        paths = [item.path for item in spec.resources.values()]
        if len(set(paths)) != len(paths) or any(
            path in reserved or path.split("/")[0] in {"src", "tests"} for path in paths
        ):
            raise ValueError("resource collides with export files")
        resources = {key: files[item.path].decode("utf-8") for key, item in spec.resources.items()}
        version = compile_snapshot(spec, resources)
        if version.lock != json.loads(files["agent.lock.json"]):
            raise ValueError("export version lock mismatch")
        bindings = json.loads(files["tool-bindings.json"])
        # Config validation is inert; imported credentials are always environment references.
        from evosprig.plugins.external_http import ExternalHTTPConfig
        from evosprig.plugins.http_tools import HTTPToolConfig
        from evosprig.plugins.mcp_tools import MCPToolConfig

        for name, binding in bindings.items():
            cls = {
                "http": HTTPToolConfig,
                "mcp": MCPToolConfig,
                "external_http": ExternalHTTPConfig,
            }.get(binding.get("kind"))
            if cls is None or cls.model_validate(binding).name != name:
                raise ValueError("unknown tool binding")
        report = compatibility_report(version, tool_bindings=bindings)
        if not report["compatible"]:
            raise ValueError("archive contains unsupported plugins")
        return version, report | {"tool_bindings": bindings, "files": len(files)}
    except (KeyError, UnicodeError, TypeError, AttributeError, yaml.YAMLError):
        raise ValueError("archive is missing valid declarative export data") from None
