"""Optional IndustryBench bridge: isolated sessions and business-state replay scoring."""

import asyncio
import importlib
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from pydantic import Field

from evosprig.core.protocols import Tool
from evosprig.core.spec import Contract


class IndustryConfig(Contract):
    root_env: str = "INDUSTRYBENCH_ROOT"
    allowed_cases: list[str] = Field(default_factory=list)
    search_limit: int = Field(default=8, ge=1, le=30)
    max_calls: int = Field(default=256, ge=1, le=1000)
    timeout_seconds: float = Field(default=30, gt=0, le=300)


def load_backend(config):
    """Only deployment configuration selects code; samples carry case IDs, never paths."""
    root = os.environ.get(config.root_env)
    if root:
        root = Path(root).resolve(strict=True)
        if not (root / "industrybench" / "session.py").is_file():
            raise ValueError("INDUSTRYBENCH_ROOT must contain the industrybench package")
        loaded = sys.modules.get("industrybench")
        if loaded and Path(loaded.__file__).resolve().parent.parent != root:
            raise ValueError("a different IndustryBench installation is already loaded")
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    try:
        session = importlib.import_module("industrybench.session").Session
        registry = importlib.import_module("industrybench.registry")
        evaluate = importlib.import_module("industrybench.evaluation").evaluate
    except ImportError as exc:
        raise ValueError(
            "Install IndustryBench or set INDUSTRYBENCH_ROOT before evaluation"
        ) from exc
    return session, registry, evaluate


class IndustryEnvironment:
    """Writes are confined to a fresh benchmark sandbox for each evaluation sample."""

    allow_writes = True

    def __init__(self, config=None, *, backend=None):
        self.config = config or IndustryConfig()
        self.session_factory, self.registry, self.evaluate = backend or load_backend(self.config)
        self.sessions = {}

    def permits(self, tool):
        return tool.side_effect == "read_only" or tool.name == "industry.invoke"

    async def prepare(self, scope, sample, tools):
        case_id = sample.input.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("industry tasks require input.case_id")
        if self.config.allowed_cases and case_id not in self.config.allowed_cases:
            raise ValueError("industry case is outside the deployment allowlist")
        # One worker per session also supports engines with thread-affine SQLite.
        # Register it before awaiting initialization so cancellation always cleans up.
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="industry-case")
        lock = threading.RLock()
        calls, discovered = [], set()
        state = {"executor": executor, "lock": lock, "calls": calls, "case_id": case_id}
        self.sessions[scope] = state

        def initialize():
            state["session"] = self.session_factory(case_id)
            return state["session"]

        session = await asyncio.get_running_loop().run_in_executor(executor, initialize)

        def on_session(function):
            async def call(**kwargs):
                return await asyncio.get_running_loop().run_in_executor(
                    executor, partial(function, **kwargs)
                )

            return call

        def materials():
            with lock:
                # SOP plus observation; discover schemas on demand instead of sending
                # hundreds of tool definitions on every model request.
                return {
                    "industry": session.industry,
                    "task": session.observation(),
                    "sop": self.registry.sop(session.industry, session.case),
                }

        def search(query, limit=None):
            with lock:
                matches = session.search(
                    query, limit=min(limit or self.config.search_limit, self.config.search_limit)
                )
                discovered.update(item["function"]["name"] for item in matches)
                return {"tools": matches}

        def invoke(name, arguments, idempotency_key):
            with lock:
                if name not in discovered:
                    return {"ok": False, "error": "Discover the tool schema before calling it"}
                if len(calls) >= self.config.max_calls:
                    return {"ok": False, "error": "Environment call budget exhausted"}
                response = session.call(name, arguments, idempotency_key=idempotency_key)
                calls.append(
                    {
                        "tool": name,
                        "arguments": arguments,
                        "idempotency_key": idempotency_key,
                        "response": response,
                    }
                )
                return response

        obj = {"type": "object"}
        tools.register(
            Tool(
                "industry.materials",
                "Read the task and its operating procedure",
                {**obj, "additionalProperties": False},
                obj,
                on_session(materials),
                timeout_seconds=self.config.timeout_seconds,
            )
        )
        tools.register(
            Tool(
                "industry.search",
                "Discover business tool schemas by name or purpose",
                {
                    **obj,
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 30},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                obj,
                on_session(search),
                timeout_seconds=self.config.timeout_seconds,
            )
        )
        tools.register(
            Tool(
                "industry.invoke",
                "Call a discovered tool in the task's sandbox",
                {
                    **obj,
                    "properties": {"name": {"type": "string"}, "arguments": obj},
                    "required": ["name", "arguments"],
                    "additionalProperties": False,
                },
                obj,
                on_session(invoke),
                side_effect="write",
                idempotent=True,
                timeout_seconds=self.config.timeout_seconds,
            )
        )
        return tools

    async def observe(self, scope, sample, result):
        state = self.sessions[scope]

        def snapshot():
            with state["lock"]:
                session = state["session"]
                prediction = {
                    "case_id": state["case_id"],
                    "industry": session.industry,
                    "calls": list(state["calls"]),
                    "final_state": session.env.final_state(),
                }
                # Scores come from replayed effects, never the model's success claim.
                report = self.evaluate(
                    [prediction], industry=session.industry, ids=[state["case_id"]]
                )
                return {
                    "case_id": state["case_id"],
                    "industry": session.industry,
                    "calls": list(state["calls"]),
                    "business_report": report,
                }

        return await asyncio.get_running_loop().run_in_executor(state["executor"], snapshot)

    async def cleanup(self, scope):
        state = self.sessions.pop(scope, None)
        if state:

            def close():
                with state["lock"]:
                    if "session" in state:
                        state["session"].close()

            try:
                await asyncio.get_running_loop().run_in_executor(state["executor"], close)
            finally:
                state["executor"].shutdown(wait=False)


def industry_score(payload):
    report = payload["observations"]["environment"]["business_report"]
    summary = report["summary"]
    if summary.get("service_fault_cases"):
        raise ValueError("Industry environment service failed; assessment is incomplete")
    score = float(summary["task_success_rate"])
    # Keep evaluator feedback concise; gold/reference execution is never sent to the agent.
    return {
        "score": score,
        "feedback": "Business-state replay passed"
        if score == 1
        else "Business-state replay failed; inspect the environment report and tool observations",
        "evidence": ["Replayed recorded calls against frozen business answers"],
    }
