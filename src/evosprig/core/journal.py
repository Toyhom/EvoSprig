"""Persistence contract and an in-memory implementation for portable execution."""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol

from jsonschema import Draft202012Validator

from .protocols import ExecutionError
from .spec import canonical_json
from .version import AgentVersion

TERMINAL = frozenset({"succeeded", "failed", "canceled"})


class LeaseConflict(ExecutionError):
    code = "lease_conflict"


class LeaseLost(ExecutionError):
    code = "lease_lost"


@dataclass(frozen=True)
class Scope:
    project: str
    user: str = "local"
    tenant: str = "local"

    def __post_init__(self):
        if any(
            not isinstance(value, str) or not value or len(value) > 128
            for value in (self.project, self.user, self.tenant)
        ):
            raise ValueError("scope identities must be nonempty bounded strings")

    @property
    def key(self) -> str:
        return canonical_json(asdict(self))


@dataclass(frozen=True)
class Lease:
    run_id: str
    owner: str
    generation: int


def initial_checkpoint() -> dict:
    return {
        "nodes": {},
        "responses": {},
        "output": None,
        "error": None,
        "waiting": [],
        "active_seconds": 0.0,
        "started": False,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "model_calls": 0,
            "unreported_model_calls": 0,
            "reserved_tokens": 0,
            "steps": 0,
            "cost": None,
            "currency": None,
        },
    }


def new_run(run_id: str, version: AgentVersion, inputs: dict, scope: Scope, metadata: dict) -> dict:
    if scope.project != version.spec.id:
        raise ValueError("run scope must match the version's project")
    now = time.time()
    return {
        "run_id": run_id,
        "version": asdict(version),
        "input": copy.deepcopy(inputs),
        "scope": asdict(scope),
        "metadata": copy.deepcopy(metadata),
        "status": "queued",
        "checkpoint": initial_checkpoint(),
        "owner": None,
        "generation": 0,
        "lease_until": 0.0,
        "cancel_requested": False,
        "created_at": now,
        "updated_at": now,
        "ready_at": now,
    }


def check_lease(record: dict, lease: Lease) -> None:
    if (
        record["owner"] != lease.owner
        or record["generation"] != lease.generation
        or record["lease_until"] <= time.time()
    ):
        raise LeaseLost("worker lease expired or was superseded")


def make_event(record: dict, sequence: int, event: dict) -> dict:
    return {
        "event_version": "0.2",
        "event_id": f"{record['run_id']}:{sequence}",
        "run_id": record["run_id"],
        "agent_version": record["version"]["version_id"],
        "sequence": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node_id": event.get("node_id"),
        "type": event["type"],
        "data": event.get("data", {}),
    }


def validate_response(record, path, response):
    waiting = next((item for item in record["checkpoint"]["waiting"] if item["path"] == path), None)
    if (
        record["status"] not in {"waiting_input", "queued"}
        or record.get("owner") is not None
        or waiting is None
        or waiting["kind"] not in {"human", "operation_unknown"}
        or path in record["checkpoint"]["responses"]
    ):
        raise ValueError("run is not waiting for this response")
    canonical_json(response)
    Draft202012Validator(waiting.get("schema", {})).validate(response)


class RunJournal(Protocol):
    durable: bool

    def create(
        self, run_id: str, version: AgentVersion, inputs: dict, scope: Scope, metadata: dict
    ) -> dict: ...
    def get(self, run_id: str, scope: Scope | None = None) -> dict: ...
    def control(self, run_id: str, scope: Scope | None = None) -> dict: ...
    def claim(self, run_id: str, owner: str, lease_seconds: float) -> Lease: ...
    def heartbeat(self, lease: Lease, lease_seconds: float) -> None: ...
    def save(
        self,
        lease: Lease,
        checkpoint: dict,
        status: str,
        events: list[dict],
        *,
        release: bool = False,
        delay: float = 0,
    ) -> list[dict]: ...
    def events(self, run_id: str, after: int = 0) -> list[dict]: ...
    def operation(
        self,
        lease: Lease,
        operation_id: str,
        intent: dict | None = None,
        update: dict | None = None,
    ) -> dict | None: ...
    def cancel(self, run_id: str, scope: Scope | None = None) -> None: ...
    def respond(
        self, run_id: str, path: str, response: dict, scope: Scope | None = None
    ) -> None: ...
    def due(self, limit: int = 100) -> list[str]: ...


class MemoryJournal:
    durable = False

    def __init__(self):
        self._runs: dict[str, dict] = {}
        self._events: dict[str, list] = {}
        self._operations: dict[tuple, dict] = {}
        self._lock = threading.RLock()

    def create(self, run_id, version, inputs, scope, metadata):
        with self._lock:
            candidate = new_run(run_id, version, inputs, scope, metadata)
            if run_id in self._runs:
                record = self._runs[run_id]
                if any(
                    record[key] != candidate[key]
                    for key in ("version", "input", "scope", "metadata")
                ):
                    raise ValueError("run ID already belongs to a different execution")
            else:
                self._runs[run_id] = candidate
                self._events[run_id] = []
            return self.get(run_id, scope)

    def get(self, run_id, scope=None):
        with self._lock:
            record = self._runs[run_id]
            if scope is not None and record["scope"] != asdict(scope):
                raise KeyError("run not found in scope")
            return copy.deepcopy(record)

    def control(self, run_id, scope=None):
        with self._lock:
            record = self._runs[run_id]
            if scope is not None and record["scope"] != asdict(scope):
                raise KeyError("run not found in scope")
            return {key: record[key] for key in (
                "owner", "generation", "lease_until", "cancel_requested", "status",
            )}

    def claim(self, run_id, owner, lease_seconds=30.0):
        with self._lock:
            record = self._runs[run_id]
            if record["status"] in TERMINAL or (
                record["status"] == "waiting_input" and not record["cancel_requested"]
            ):
                raise LeaseConflict("run cannot be claimed in its current state")
            if record["owner"] is not None and record["lease_until"] > time.time():
                raise LeaseConflict("another worker holds the run lease")
            if lease_seconds <= 0:
                raise ValueError("lease must be positive")
            record.update(
                owner=owner,
                generation=record["generation"] + 1,
                lease_until=time.time() + lease_seconds,
                status="running",
            )
            return Lease(run_id, owner, record["generation"])

    def heartbeat(self, lease, lease_seconds=30.0):
        with self._lock:
            record = self._runs[lease.run_id]
            check_lease(record, lease)
            record["lease_until"] = time.time() + lease_seconds

    def save(self, lease, checkpoint, status, events, *, release=False, delay=0):
        with self._lock:
            record = self._runs[lease.run_id]
            check_lease(record, lease)
            record.update(
                checkpoint=copy.deepcopy(checkpoint),
                status=status,
                updated_at=time.time(),
                ready_at=time.time() + delay,
            )
            added = [
                make_event(record, len(self._events[lease.run_id]) + i + 1, event)
                for i, event in enumerate(events)
            ]
            self._events[lease.run_id].extend(added)
            if release:
                record.update(owner=None, lease_until=0.0)
            return copy.deepcopy(added)

    def events(self, run_id, after=0):
        with self._lock:
            return copy.deepcopy(
                [event for event in self._events[run_id] if event["sequence"] > after]
            )

    def operation(self, lease, operation_id, intent=None, update=None):
        with self._lock:
            check_lease(self._runs[lease.run_id], lease)
            key = (lease.run_id, operation_id)
            if key not in self._operations and intent is not None:
                self._operations[key] = {
                    "id": operation_id,
                    "status": "intent",
                    "intent": copy.deepcopy(intent),
                }
            if update is not None:
                if key not in self._operations:
                    raise KeyError("operation intent is missing")
                self._operations[key].update(copy.deepcopy(update))
            return copy.deepcopy(self._operations.get(key))

    def cancel(self, run_id, scope=None):
        with self._lock:
            self.get(run_id, scope)
            record = self._runs[run_id]
            if record["status"] in TERMINAL:
                return
            record["cancel_requested"] = True

    def respond(self, run_id, path, response, scope=None):
        with self._lock:
            self.get(run_id, scope)
            record = self._runs[run_id]
            validate_response(record, path, response)
            record["checkpoint"]["responses"][path] = copy.deepcopy(response)
            record["status"] = "queued"
            record["ready_at"] = time.time()

    def due(self, limit=100):
        with self._lock:
            now = time.time()
            return [
                key
                for key, value in self._runs.items()
                if (
                    value["status"] in {"queued", "running", "waiting_external"}
                    or (value["status"] == "waiting_input" and value["cancel_requested"])
                )
                and value["lease_until"] <= now
                and value["ready_at"] <= now
            ][:limit]
