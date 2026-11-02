"""One thread-safe budget shared by optimization and all evaluation model calls."""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import asdict, replace

from pydantic import Field

from evosprig.core.protocols import BudgetExceeded, ProviderError
from evosprig.core.spec import Contract, canonical_json


class ExperimentBudget(Contract):
    max_evaluations: int = Field(default=100, ge=1, le=100000)
    max_model_calls: int = Field(default=200, ge=1, le=100000)
    max_total_tokens: int = Field(default=200000, ge=512, le=100000000)
    max_seconds: float = Field(default=600.0, gt=0, le=86400)
    max_candidates: int = Field(default=5, ge=1, le=1000)
    proposal_output_tokens: int = Field(default=1024, ge=64, le=16384)


class BudgetMeter:
    def __init__(self, limits: ExperimentBudget, *, on_change=None, state=None):
        self.limits = limits
        self.lock = threading.RLock()
        self.canceled = threading.Event()
        self.started = time.monotonic()
        self.on_change = on_change
        self.state = state or {
            "evaluations": 0,
            "candidates": 0,
            "model_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reserved_tokens": 0,
            "unreported_model_calls": 0,
            "elapsed_seconds": 0.0,
            "cost": None,
            "currency": None,
        }
        self.previous_elapsed = self.state["elapsed_seconds"]

    def snapshot(self):
        with self.lock:
            self.state["elapsed_seconds"] = self.previous_elapsed + time.monotonic() - self.started
            return copy.deepcopy(self.state)

    def changed(self):
        if self.on_change:
            self.on_change(self.snapshot())

    def check(self):
        if self.canceled.is_set():
            raise BudgetExceeded("experiment canceled", scope="experiment")
        if self.snapshot()["elapsed_seconds"] >= self.limits.max_seconds:
            raise BudgetExceeded("experiment time budget exhausted", scope="experiment")

    def consume(self, kind, count=1):
        with self.lock:
            self.check()
            if kind not in {"evaluations", "candidates"} or count < 0:
                raise ValueError("invalid budget counter")
            if self.state[kind] + count > getattr(self.limits, "max_" + kind):
                raise BudgetExceeded(f"experiment {kind} budget exhausted", scope="experiment")
            self.state[kind] += count
            self.changed()

    def reserve(self, request):
        with self.lock:
            self.check()
            if self.state["model_calls"] >= self.limits.max_model_calls:
                raise BudgetExceeded("experiment model-call budget exhausted", scope="experiment")
            estimate = len(canonical_json(asdict(request)).encode()) + 256
            remaining = (
                self.limits.max_total_tokens
                - self.state["input_tokens"]
                - self.state["output_tokens"]
                - self.state["reserved_tokens"]
            )
            allowance = min(request.max_output_tokens, remaining - estimate)
            if allowance < 1:
                raise BudgetExceeded(
                    "experiment token budget cannot reserve another call", scope="experiment"
                )
            reservation = estimate + allowance
            self.state["model_calls"] += 1
            self.state["reserved_tokens"] += reservation
            self.state["unreported_model_calls"] += 1
            self.changed()
            return replace(request, max_output_tokens=allowance), reservation

    def settle(self, reservation, usage):
        with self.lock:
            self.state["reserved_tokens"] -= reservation
            self.state["unreported_model_calls"] -= 1
            self.state["input_tokens"] += usage.input_tokens
            self.state["output_tokens"] += usage.output_tokens
            self.changed()
            if (
                self.state["input_tokens"]
                + self.state["output_tokens"]
                + self.state["reserved_tokens"]
                > self.limits.max_total_tokens
            ):
                raise BudgetExceeded(
                    "provider usage exceeded the reserved experiment budget", scope="experiment"
                )


class BudgetedProvider:
    def __init__(self, provider, meter):
        self.provider, self.meter = provider, meter
        self.model_id, self.capabilities = provider.model_id, provider.capabilities
        if hasattr(provider, "connection"):
            self.connection = provider.connection

    def session(self):
        from evosprig.core.model_sessions import model_sessions

        return model_sessions([self.provider])

    async def complete(self, request):
        requested = request.max_output_tokens
        request, reservation = self.meter.reserve(request)
        # Failed/canceled calls keep their reservation: unreported usage is not free.
        try:
            response = await self.provider.complete(request)
        except ProviderError as exc:
            if exc.code == "output_limit" and request.max_output_tokens < requested:
                raise BudgetExceeded(
                    "experiment token allowance truncated a response", scope="experiment"
                ) from None
            raise
        self.meter.settle(reservation, response.usage)
        return response
