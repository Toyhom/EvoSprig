"""Build a native workflow from your local industry's synthesis templates."""
import argparse
from pathlib import Path

from evosprig.industry_cli import synthesis_project

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--templates", type=Path, required=True)
    parser.add_argument("--scene", default="government")
    parser.add_argument("--out", type=Path, default=Path("environment-builder"))
    args = parser.parse_args()
    synthesis_project(args.out, template_root=args.templates, scene=args.scene)
