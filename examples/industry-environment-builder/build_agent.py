"""Copy the starter workflow, or build from your industry's synthesis templates."""
import argparse
import shutil
from pathlib import Path

from evosprig.industry_cli import synthesis_project

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--templates", type=Path)
    parser.add_argument("--scene", default="government")
    parser.add_argument("--out", type=Path, default=Path("environment-builder"))
    args = parser.parse_args()
    if args.templates:
        synthesis_project(args.out, template_root=args.templates, scene=args.scene)
    else:
        source = Path(__file__).resolve().parent
        args.out.mkdir(parents=True, exist_ok=False)
        shutil.copy2(source / "agent.yaml", args.out / "agent.yaml")
        shutil.copytree(source / "prompts", args.out / "prompts")
