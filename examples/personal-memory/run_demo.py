"""A persistent assistant with explicit profile, facts and changing relationships."""

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
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_memory import SQLiteMemory
from evosprig.plugins.structured_memory import StructuredMemory


class MemoryFixture(MockProvider):
    async def complete(self, request):
        self.requests.append(request)
        data = json.loads(request.messages[-1]["content"])
        relation = data["relations"]["relations"][0]["metadata"]["relation"]
        return ModelResponse(text=f"{relation[0]} now works on {relation[2]}.", model=self.model_id)


async def demo(workspace, live=False):
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).parent
    spec = load_spec(root / "agent.yaml")
    identity = Scope(spec.id)
    scope = MemoryScope(identity)
    memory = SQLiteMemory(workspace / "memory.sqlite")
    structured = StructuredMemory(memory)
    if not structured.context(scope)["blocks"]:
        structured.set_context(
            scope, "profile", "Alice prefers concise English answers.", source="user:explicit"
        )
        structured.set_relation(
            scope, "Alice", "works_on", "Orion", source="conversation:1", valid_from=100
        )
        structured.set_relation(
            scope, "Alice", "works_on", "Atlas", source="conversation:2", valid_from=200
        )
    memory.write(scope, "Project Atlas is a research assistant.", source="project:atlas")
    # A new store instance demonstrates that the next session retains user state.
    runtime = Runtime(
        make_models(spec) if live else {"main": MemoryFixture()}, make_tools(workspace, identity)
    )
    result = await runtime.run(
        compile_agent(spec, root),
        {"question": "Which project does Alice work on now?", "subject": "Alice"},
    )
    report = {
        "mode": "live-model" if live else "offline-contract",
        "status": result.status,
        "output": result.output,
        "historical_project": structured.relations(scope, "Alice", at=150)[0]["metadata"][
            "relation"
        ][2],
    }
    (workspace / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(demo(args.workspace, args.live)), indent=2))
