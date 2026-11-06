"""Create a reproducible product-source ZIP, dependency inventory and checksums."""

import argparse
import hashlib
import json
import tomllib
import zipfile
from pathlib import Path

from audit import check, source_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root.resolve()
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"evosprig-{version}-source.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in source_files(root):
            name = file.relative_to(root).as_posix()
            data = file.read_bytes()
            check(name, data)
            info = zipfile.ZipInfo(name, (2026, 11, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    packages = []
    for line in (root / "requirements-dev.lock").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, pinned = line.split("==")
        packages.append(
            {
                "SPDXID": "SPDXRef-pypi-" + name,
                "name": name,
                "versionInfo": pinned,
                "downloadLocation": f"https://pypi.org/project/{name}/{pinned}/",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
            }
        )
    for lockfile in sorted((root / "apps").glob("*/package-lock.json")):
        npm = json.loads(lockfile.read_text())
        for key, item in sorted(npm["packages"].items()):
            if not key:
                continue
            packages.append(
                {
                    "SPDXID": "SPDXRef-npm-"
                    + hashlib.sha256((lockfile.parent.name + ":" + key).encode()).hexdigest()[:16],
                    "name": key.split("node_modules/")[-1],
                    "versionInfo": item["version"],
                    "downloadLocation": item.get("resolved", "NOASSERTION"),
                    "filesAnalyzed": False,
                    "licenseConcluded": "NOASSERTION",
                    "licenseDeclared": item.get("license", "NOASSERTION"),
                }
            )
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "EvoSprig locked development and runtime dependencies",
        "documentNamespace": "https://evosprig.invalid/spdx/"
        + hashlib.sha256(json.dumps(packages, sort_keys=True).encode()).hexdigest(),
        "creationInfo": {
            "created": "2026-11-02T00:00:00Z",
            "creators": ["Tool: EvoSprig release packager"],
        },
        "packages": packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": item["SPDXID"],
            }
            for item in packages
        ],
    }
    (args.out / "sbom.spdx.json").write_text(json.dumps(sbom, indent=2) + "\n")
    files = [
        file for file in sorted(args.out.iterdir()) if file.is_file() and file.name != "SHA256SUMS"
    ]
    (args.out / "SHA256SUMS").write_text(
        "".join(
            hashlib.sha256(file.read_bytes()).hexdigest() + "  " + file.name + "\n"
            for file in files
        )
    )
    print(
        json.dumps(
            {
                "source_archive": path.name,
                "files": {file.name: file.stat().st_size for file in files},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
