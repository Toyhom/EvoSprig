"""Prepare native industry agents, replay suites and reviewed synthesis workflows."""

import json
import random
from pathlib import Path

import yaml

from evosprig.core.spec import save_spec
from evosprig.evaluation.industry import IndustryConfig, load_backend
from evosprig.evaluation.suite import EvalSuite
from evosprig.sdk import Builder

OBJECT = {"type": "object"}
TEXT = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
INSTRUCTIONS = """Complete the industry case using the provided operating procedure.
Read the task materials first. Discover tool schemas before invoking them. Inspect
actual evidence and tool responses, handle version conflicts by rereading state,
and honor approval, review, transaction and call-budget requirements. Never infer
success from prose: verify the recorded business outcome. Give a concise account
of completed actions, unresolved requirements and the final state. Do not invent
facts, tool names, arguments or successful operations.
"""


def industry_agent(project_id="industry-assistant"):
    b = Builder(
        project_id,
        {**OBJECT, "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        TEXT,
        spec_version="0.3",
    )
    b.model("main", "main-model", ["text", "tool_calling"])
    for name in ("materials", "search", "invoke"):
        b.tool(name, "industry." + name)
    b.resource("procedure", "prompts/procedure.md")
    b.node("read_procedure", "tool", tool="materials", output_schema=OBJECT)
    b.node(
        "specialist",
        "agent",
        model="main",
        tools=["search", "invoke"],
        instructions={"resource": "procedure"},
        inputs={
            "case_id": {"ref": "input.case_id"},
            "materials": {"ref": "nodes.read_procedure.output"},
        },
        output_schema=TEXT,
        max_tool_rounds=192,
        tool_errors="feedback",
    )
    b.edge("read_procedure", "specialist").output(text={"ref": "nodes.specialist.output.text"})
    return b.execution(
        max_steps=600,
        max_model_calls=200,
        max_total_tokens=1000000,
        max_output_tokens=2048,
        timeout_seconds=1800,
        allow_side_effects=True,
    ).build_spec()


def prepare_project(out, *, config=None, industry="government", limit=12, seed=0):
    config = config or IndustryConfig()
    _, registry, _ = load_backend(config)
    selected = registry.select(industry, ids=config.allowed_cases or None, limit=limit)
    ids = [registry.case_id(case) for _, case in selected]
    if len(ids) < 4:
        raise ValueError("Provide at least four distinct cases for search, selection and release")
    random.Random(seed).shuffle(ids)
    samples = [{"id": f"case-{i + 1}", "input": {"case_id": cid}} for i, cid in enumerate(ids)]
    cut = max(1, min(len(ids) // 2, len(ids) - 3))
    suite = EvalSuite.model_validate(
        {
            "id": "industry-tasks",
            "metric": {
                "kind": "external",
                "scorer": "industry",
                "target": "environment",
                "output_path": "",
            },
            "search": samples[:cut],
            "selection": samples[cut:-2],
            "release": samples[-2:],
        }
    )
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "prompts").mkdir()
    (out / "prompts/procedure.md").write_text(INSTRUCTIONS)
    save_spec(industry_agent(), out / "agent.yaml")
    (out / "suite.yaml").write_text(
        yaml.safe_dump(
            suite.model_dump(mode="json", by_alias=True, exclude_defaults=True), sort_keys=False
        )
    )
    deployment = {
        "models": {
            "main-model": {
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-flash",
                "api_key_env": "DEEPSEEK_API_KEY",
            }
        },
        "evaluation": {"industry": {**config.model_dump(), "allowed_cases": ids}},
    }
    (out / "deployment.yaml").write_text(yaml.safe_dump(deployment, sort_keys=False))
    return {"project": str(out), "cases": len(ids), "suite_id": suite.suite_id}


def synthesis_project(out, *, template_root, scene):
    """Produce editable drafts with the team's local templates, using normal nodes."""
    stages = [
        ("context", "Context_Generation"),
        ("schema", "Schema_Generation"),
        ("sop", "SOP_Generation"),
        ("api_graph", "API_Graph_Generation"),
        ("dataset", "Dataset_Generation"),
        ("api", "SOP_API_Generation"),
        ("implementation", "SOP_API_Function_Code"),
    ]
    templates = Path(template_root).resolve()
    if scene not in {
        "loan",
        "account",
        "credit_cards",
        "deposit",
        "invest",
        "government",
        "manufacturing",
    }:
        raise ValueError("Unknown synthesis scene")
    prompts = {}
    for name, filename in stages:
        raw = yaml.safe_load((templates / scene / "prompts" / (filename + ".yaml")).read_text())
        section = raw.get("prompts", {})
        text_parts = [str(raw[key]) for key in ("system_prompt", "user_prompt") if raw.get(key)]
        if isinstance(section, dict):
            text_parts.extend(
                value
                for key, value in section.items()
                if key.startswith("text") and isinstance(value, str)
            )
        prompts[name] = (
            (
                "The task input contains the requested scenario and outputs from earlier stages. "
                "Resolve template placeholders using those fields; retain explicit business constraints.\n\n"
                + "\n\n".join(text_parts)
            )
            if text_parts
            else ""
        )
        if not prompts[name].strip():
            raise ValueError("Synthesis template is empty")
    b = Builder(
        "industry-environment-builder",
        {**OBJECT, "properties": {"brief": {"type": "string"}}, "required": ["brief"]},
        OBJECT,
        spec_version="0.3",
    ).model("main", "main-model")
    previous = None
    for index, (name, _) in enumerate(stages):
        b.resource(name, f"prompts/{name}.md")
        inputs = {"brief": {"ref": "input.brief"}}
        inputs.update({stage: {"ref": f"nodes.{stage}.output.text"} for stage, _ in stages[:index]})
        b.node(
            name,
            "model",
            model="main",
            instructions={"resource": name},
            inputs=inputs,
            output_schema=TEXT,
        )
        if previous:
            b.edge(previous, name)
        previous = name
    b.node(
        "review_environment",
        "human",
        inputs={name: {"ref": f"nodes.{name}.output.text"} for name, _ in stages},
        output_schema={
            **OBJECT,
            "properties": {"approved": {"const": True}, "notes": {"type": "string"}},
            "required": ["approved"],
        },
    )
    b.edge(previous, "review_environment")
    b.data["graph"]["output"] = {name: {"ref": f"nodes.{name}.output.text"} for name, _ in stages}
    b.data["graph"]["output"]["review"] = {"ref": "nodes.review_environment.output"}
    spec = b.execution(
        max_model_calls=7, max_output_tokens=8192, max_total_tokens=200000, timeout_seconds=1200
    ).build_spec()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "prompts").mkdir()
    for name, content in prompts.items():
        (out / f"prompts/{name}.md").write_text(content)
    save_spec(spec, out / "agent.yaml")
    return {"project": str(out), "stages": len(stages), "review_node": "graph/review_environment"}


def add_commands(commands):
    parser = commands.add_parser("industry", help="Connect an IndustryBench environment")
    sub = parser.add_subparsers(dest="industry_command", required=True)
    prepare = sub.add_parser(
        "prepare", help="Create an agent and disjoint business evaluation suite"
    )
    prepare.add_argument("--out", type=Path, required=True)
    prepare.add_argument(
        "--industry", choices=["finance", "government", "manufacturing"], default="government"
    )
    prepare.add_argument("--limit", type=int, default=12)
    prepare.add_argument("--seed", type=int, default=0)
    synth = sub.add_parser("synthesis", help="Create a reviewed environment drafting workflow")
    synth.add_argument("--out", type=Path, required=True)
    synth.add_argument("--templates", type=Path, required=True)
    synth.add_argument("--scene", required=True)


def run_command(args):
    if args.industry_command == "prepare":
        result = prepare_project(args.out, industry=args.industry, limit=args.limit, seed=args.seed)
    else:
        result = synthesis_project(args.out, template_root=args.templates, scene=args.scene)
    print(json.dumps(result, indent=2))
