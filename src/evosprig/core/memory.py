"""Scoped memory and retrieval contracts, independent of storage implementations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

from pydantic import Field, model_validator

from .journal import Scope
from .spec import Contract, canonical_json


@dataclass(frozen=True)
class MemoryScope:
    identity: Scope
    role: str = "assistant"
    namespace: str = "default"

    def __post_init__(self):
        for value in (self.role, self.namespace):
            if not isinstance(value, str) or not value or len(value) > 128:
                raise ValueError("memory scope components must be nonempty bounded strings")

    @property
    def key(self) -> str:
        return canonical_json(asdict(self))


class MemoryRecord(Contract):
    id: str = Field(min_length=1, max_length=128)
    scope: dict
    content: str = Field(min_length=1, max_length=100_000)
    content_type: Literal["fact", "experience", "document", "context"] = "fact"
    source: str = Field(min_length=1, max_length=2048)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0, le=1)
    created_at: float
    updated_at: float
    valid_from: float | None = None
    valid_until: float | None = None
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_record(self):
        canonical_json(self.model_dump())
        for key in ("derived_from", "links"):
            values = self.metadata.get(key, [])
            if (
                not isinstance(values, list)
                or len(values) > 32
                or any(not isinstance(value, str) or not 1 <= len(value) <= 128 for value in values)
            ):
                raise ValueError("memory references must be bounded record IDs")
        revisions = self.metadata.get("derived_revisions", {})
        if (
            not isinstance(revisions, dict)
            or len(revisions) > 32
            or any(
                not isinstance(key, str) or not isinstance(value, int) or value < 1
                for key, value in revisions.items()
            )
        ):
            raise ValueError("invalid source memory revisions")
        if self.valid_from is not None and self.valid_until is not None:
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must follow valid_from")
        return self


class MemoryConflict(ValueError):
    pass


class MemoryStore(Protocol):
    capabilities: frozenset[str]

    def write(self, scope: MemoryScope, content: str, *, source: str, **kwargs) -> dict: ...
    def get(self, scope: MemoryScope, record_id: str) -> dict: ...
    def search(self, scope: MemoryScope, query: str, *, limit: int = 5) -> list[dict]: ...
    def update(
        self, scope: MemoryScope, record_id: str, content: str, *, revision: int
    ) -> dict: ...
    def delete(self, scope: MemoryScope, record_id: str) -> None: ...
    def export(self, scope: MemoryScope) -> list[dict]: ...
    def namespace_delete(self, scope: MemoryScope) -> int: ...


class Retriever(Protocol):
    def search(self, scope: MemoryScope, query: str, *, limit: int = 5) -> list[dict]: ...
