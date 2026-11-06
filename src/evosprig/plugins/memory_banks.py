"""Named persistent agent memories, configured independently from business documents."""

import json
import re
from typing import Literal

from pydantic import Field, model_validator

from evosprig.core.memory import MemoryScope
from evosprig.core.spec import Contract
from evosprig.plugins.embeddings import EmbeddingConnection, OpenAIEmbeddings
from evosprig.plugins.semantic_memory import HybridMemory

BANK_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
OPERATIONS = frozenset({"search", "write", "recall", "remember", "summarize", "context", "relations"})


def memory_plugin(bank, operation):
    if not BANK_NAME.fullmatch(bank) or operation not in OPERATIONS:
        raise ValueError("invalid memory bank or operation")
    return f"memory.{operation}" if bank == "default" else f"memory.{bank}.{operation}"


def plugin_bank(plugin):
    parts = plugin.split(".")
    if len(parts) == 2 and parts[0] == "memory" and parts[1] in OPERATIONS:
        return "default"
    if len(parts) == 3 and parts[0] == "memory" and parts[1] != "default" and BANK_NAME.fullmatch(parts[1]) and parts[2] in OPERATIONS:
        return parts[1]
    return None


class MemoryBankConfig(Contract):
    retrieval: Literal["lexical", "semantic", "hybrid"] = "lexical"
    embeddings: EmbeddingConnection | None = None
    min_similarity: float | None = Field(default=None, ge=-1, le=1, allow_inf_nan=False)
    embedding_batch_size: int = Field(default=64, ge=1, le=256)
    embedding_cache_entries: int = Field(default=100000, ge=1)
    retrieval_timeout_seconds: float = Field(default=120, gt=0, allow_inf_nan=False)
    agent_writes: bool = True

    @model_validator(mode="after")
    def connection_required(self):
        if self.retrieval != "lexical" and self.embeddings is None:
            raise ValueError("vector memory retrieval needs an embeddings connection")
        return self


class MemoryBanksConfig(Contract):
    banks: dict[str, MemoryBankConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_names(self):
        if any(not BANK_NAME.fullmatch(name) for name in self.banks):
            raise ValueError("memory bank names need 1..48 letters, digits, underscores or hyphens, starting with a letter")
        self.banks.setdefault("default", MemoryBankConfig())
        return self


class MemoryBanks:
    """Store configuration per identity; each bank has a separate memory namespace."""

    def __init__(self, memory, config=None):
        self.memory = memory
        self.defaults = MemoryBanksConfig.model_validate(config or {})
        with memory._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS memory_bank_settings(scope TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def config(self, identity):
        with self.memory._transaction(False) as db:
            row = db.execute("SELECT body FROM memory_bank_settings WHERE scope=?", (MemoryScope(identity).key,)).fetchone()
        banks = self.defaults.model_dump()["banks"]
        banks.update(json.loads(row[0]) if row else {})
        return MemoryBanksConfig.model_validate({"banks": banks})

    def configure(self, identity, bank, values):
        memory_plugin(bank, "search")
        config = MemoryBankConfig.model_validate(values)
        with self.memory._transaction() as db:
            key = MemoryScope(identity).key
            row = db.execute("SELECT body FROM memory_bank_settings WHERE scope=?", (key,)).fetchone()
            banks = json.loads(row[0]) if row else {}
            banks[bank] = config.model_dump()
            db.execute("INSERT INTO memory_bank_settings VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET body=excluded.body", (key, json.dumps(banks)))
        return config

    def scope(self, identity, bank="default"):
        if bank not in self.config(identity).banks:
            raise KeyError("memory bank not configured")
        return MemoryScope(identity, namespace="default" if bank == "default" else "memory:" + bank)

    def backend(self, identity, bank="default"):
        config = self.config(identity).banks[bank]
        if config.retrieval == "lexical":
            return self.memory
        return HybridMemory(
            self.memory, OpenAIEmbeddings(config.embeddings), mode=config.retrieval,
            min_similarity=config.min_similarity, batch_size=config.embedding_batch_size,
            cache_path=self.memory.path.with_suffix(".memory-embeddings.sqlite"),
            persistent_cache_size=config.embedding_cache_entries,
        )
