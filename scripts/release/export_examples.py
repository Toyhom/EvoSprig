"""Build independently installable example archives with fixed public bindings."""

import argparse
import json
import zipfile
from pathlib import Path

import yaml

from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent, compile_snapshot
from evosprig.exporters.python import export_python


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    product = Path(__file__).resolve().parents[2]
    records = {}
    items = [
        ("hello", "http", None),
        ("research-assistant", "python", None),
        ("research-assistant", "python", "opro"),
        ("research-assistant", "python", "gepa"),
        ("motion-graphics", "http", None),
        ("video-studio", "http", None),
        ("research-team", "python", None),
        ("customer-support", "http", None),
        ("personal-memory", "python", None),
    ]
    for example, target, method in items:
        root = product / "examples" / example
        version = compile_agent(load_spec(root / "agent.yaml"), root)
        if method:
            version = compile_snapshot(
                version.spec,
                {
                    **version.resources,
                    "instructions": (root / "results" / (method + "-instructions.md")).read_text(),
                },
            )
        profile = root / "deployment.example.yaml"
        bindings = yaml.safe_load(profile.read_text()).get("tools", {}) if profile.exists() else {}
        name = example + ("-" + method if method else "")
        destination = args.out / name
        report = export_python(version, destination, target=target, tool_bindings=bindings)
        archive_path = args.out / (name + ".zip")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(destination.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(
                        path.relative_to(destination).as_posix(), (2026, 11, 2, 0, 0, 0)
                    )
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
        records[name] = report | {"archive_bytes": archive_path.stat().st_size}
    (args.out / "examples.json").write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
