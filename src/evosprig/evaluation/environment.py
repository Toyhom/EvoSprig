"""Per-sample environments: scoped seed data, approvals and trusted sandbox hooks."""

from typing import Protocol

from pydantic import Field

from evosprig.core.memory import MemoryScope
from evosprig.core.spec import Contract
from evosprig.plugins.documents import DocumentRetriever
from evosprig.plugins.sqlite_memory import SQLiteMemory


class DocumentSeed(Contract):
    title: str
    text: str = Field(max_length=1000000)
    source: str


class EnvironmentConfig(Contract):
    max_concurrent_samples: int = Field(default=1, ge=1, le=32)
    memory_writes: bool = False
    documents: list[DocumentSeed] = Field(default_factory=list, max_length=128)
    facts: list[str] = Field(default_factory=list, max_length=128)
    max_resumes: int = Field(default=30, ge=0, le=1000)
    poll_seconds: float = Field(default=0.2, ge=0.01, le=60)


class EvaluationEnvironment(Protocol):
    """Trusted SDK boundary. A write-enabled session must isolate effects itself."""

    allow_writes: bool

    async def prepare(self, scope, sample, tools): ...
    async def observe(self, scope, sample, result) -> dict: ...
    async def cleanup(self, scope): ...


class LocalEnvironment:
    allow_writes = False

    def __init__(self, workspace, config=None):
        self.memory = SQLiteMemory(workspace / "memory.sqlite")
        self.config = config or EnvironmentConfig()
        self.allow_writes = self.config.memory_writes

    def permits(self, tool):
        return tool.side_effect == "read_only" or (
            self.allow_writes
            and tool.name in {"memory.write", "memory.remember", "memory.summarize"}
        )

    async def prepare(self, scope, sample, tools):
        for document in self.config.documents:
            DocumentRetriever(self.memory).ingest(
                MemoryScope(scope, namespace="documents"), **document.model_dump()
            )
        for fact in self.config.facts:
            self.memory.write(MemoryScope(scope), fact, source="evaluation:seed")
        return tools

    async def observe(self, scope, sample, result):
        return {"memories": self.memory.export(MemoryScope(scope))}

    async def cleanup(self, scope):
        # Per-run identities remain isolated; retain evidence for inspection.
        pass


def approval_response(value, inputs):
    if isinstance(value, dict):
        if set(value) == {"from_input"}:
            observed = inputs
            for part in value["from_input"].split(".") if value["from_input"] else []:
                observed = observed[int(part)] if isinstance(observed, list) else observed[part]
            return observed
        return {key: approval_response(item, inputs) for key, item in value.items()}
    if isinstance(value, list):
        return [approval_response(item, inputs) for item in value]
    return value
