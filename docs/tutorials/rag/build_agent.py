"""Three native RAG graphs: python build_agent.py --mode fixed --out ./project."""
import argparse
from pathlib import Path

from evosprig.core.spec import save_spec
from evosprig.sdk import Builder

QUESTION = {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"], "additionalProperties": False}
TEXT = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}
QUERIES = {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8}}, "required": ["queries"], "additionalProperties": False}


def build(mode="fixed", project_id="rag-classroom"):
    if mode not in {"fixed", "agent", "multiquery"}:
        raise ValueError("choose fixed, agent or multiquery")
    b = Builder(project_id, QUESTION, TEXT, spec_version="0.3").default_model("main", ["text", "tool_calling", "structured_output"])
    b.tool("search", "documents.search").tool("retrieve_many", "documents.retrieve")
    b.resource("answer", "prompts/answer.md").resource("agent", "prompts/agent.md").resource("rewrite", "prompts/rewrite.md")
    if mode != "agent":
        b.resource("check_citations", "code/check_citations.py", role="code")
    if mode == "agent":
        b.node("answer", "agent", instructions={"resource": "agent"}, tools=["search"],
               inputs={"question": {"ref": "input.question"}}, response_format="text", output_schema=TEXT,
               max_tool_rounds=3, tool_errors="feedback")
    else:
        if mode == "multiquery":
            b.node("rewrite", "model", instructions={"resource": "rewrite"}, response_format="json", output_schema=QUERIES,
                   inputs={"question": {"ref": "input.question"}})
            b.node("retrieve", "tool", tool="retrieve_many", output_schema={"type": "object"},
                   inputs={"queries": {"ref": "nodes.rewrite.output.queries"}, "limit": {"value": 5}, "diversity": {"value": .3}})
            b.edge("rewrite", "retrieve")
        else:
            b.node("retrieve", "tool", tool="search", output_schema={"type": "object"},
                   inputs={"query": {"ref": "input.question"}, "limit": {"value": 5}})
        b.node("answer", "model", instructions={"resource": "answer"}, response_format="text", output_schema=TEXT,
               output_validator="check_citations", output_errors="feedback", max_output_retries=2,
               inputs={"question": {"ref": "input.question"}, "citations": {"ref": "nodes.retrieve.output.citations"}})
        b.edge("retrieve", "answer")
    b.output(text={"ref": "nodes.answer.output.text"})
    b.execution(max_model_calls=10, max_total_tokens=16000, max_output_tokens=1500, timeout_seconds=180)
    return b.build_spec()


if __name__ == "__main__":
    import shutil
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["fixed", "agent", "multiquery"], default="fixed")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).parent/"prompts", a.out/"prompts", dirs_exist_ok=True)
    shutil.copytree(Path(__file__).parent/"code", a.out/"code", dirs_exist_ok=True)
    save_spec(build(a.mode), a.out/"agent.yaml")
