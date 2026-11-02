"""Run a researcher/critic/writer team over a cited local document collection."""

import argparse
import asyncio
import json
from pathlib import Path

from evosprig.config import make_models, make_tools
from evosprig.core.journal import Scope
from evosprig.core.memory import MemoryScope
from evosprig.core.protocols import ModelResponse
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.documents import DocumentRetriever
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal
from evosprig.plugins.sqlite_memory import SQLiteMemory


class TeamFixture(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        data = json.loads(request.messages[-1]["content"])
        citations = data.get("evidence", {}).get("citations", [])
        citation = citations[0]["citation"] if citations else "[no evidence]"
        role = request.messages[0]["content"].splitlines()[0]
        text = f"{role}: Checkpoints preserve completed steps. Retry external writes with stable idempotency keys. {citation}"
        return ModelResponse(text=text, model=self.model_id)


async def demo(workspace, live=False):
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).parent
    spec = load_spec(root / "agent.yaml")
    scope = Scope(spec.id)
    memory = SQLiteMemory(workspace / "memory.sqlite")
    retriever = DocumentRetriever(memory)
    for path in sorted((root / "documents").glob("*.txt")):
        retriever.ingest(
            MemoryScope(scope, namespace="documents"),
            title=path.stem,
            text=path.read_text(),
            source="documents/" + path.name,
        )
    models = make_models(spec) if live else {"main": TeamFixture()}
    runtime = Runtime(
        models, make_tools(workspace, scope), journal=SQLiteJournal(workspace / "runs.sqlite")
    )
    result = await runtime.run(
        compile_agent(spec, root),
        {"question": "How do checkpoints and idempotency make agent workflows recoverable?"},
    )
    if result.status != "waiting_input":
        raise RuntimeError(result.error or result.status)
    draft = result.waiting[0]["input"]["draft"]
    runtime.journal.respond(result.run_id, result.waiting[0]["path"], {"text": draft})
    result = await runtime.resume(result.run_id)
    report = {
        "mode": "live-model" if live else "offline-contract",
        "status": result.status,
        "output": result.output,
        "model_calls": result.usage["model_calls"],
        "automatic_review": True,
    }
    (workspace / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(demo(args.workspace, args.live)), indent=2))
