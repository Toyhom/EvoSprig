"""Build on each target OS; include runtime source for standalone app exports."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run(
    [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", "evosprig-backend", "--distpath", str(root / "build" / "backend"),
        "--workpath", str(root / "build" / "pyinstaller"), "--specpath", str(root / "build" / "pyinstaller"),
        "--collect-all", "evosprig", "--collect-all", "uvicorn",
        "--collect-all", "jsonschema_specifications", "--collect-all", "pypdfium2",
        "--collect-all", "gepa", "--collect-submodules", "mcp.client",
        "--collect-submodules", "mcp.shared", "--copy-metadata", "mcp",
        "--copy-metadata", "evosprig", str(root / "backend.py"),
    ],
    check=True,
)
