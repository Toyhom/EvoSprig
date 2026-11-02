"""Support workflow with a transactional fixture order service and human decisions."""

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import yaml

from evosprig.config import make_models
from evosprig.core.protocols import ModelResponse, ToolRegistry
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.http_tools import HTTPToolConfig, http_tool
from evosprig.plugins.mock import MockProvider
from evosprig.plugins.sqlite_journal import SQLiteJournal


class OrderService:
    """Fixture service applies business rules independently of model instructions."""

    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS refunds (order_id TEXT UNIQUE, operation TEXT UNIQUE, amount REAL, transaction_id TEXT)"
            )

    def handle(self, request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": request.url.params["order_id"],
                    "total": 49.0,
                    "paid": True,
                    "fulfilled": False,
                    "within_window": True,
                },
            )
        payload = json.loads(request.content)
        if payload["order_id"] != "order-101" or not 0 < payload["amount"] <= 49:
            return httpx.Response(422, json={"error": "refund violates order policy"})
        key = request.headers["idempotency-key"]
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT operation, amount, transaction_id FROM refunds WHERE order_id=?",
                (payload["order_id"],),
            ).fetchone()
            if old and (old[0] != key or old[1] != payload["amount"]):
                return httpx.Response(409, json={"error": "order already refunded"})
            transaction = old[2] if old else "refund-" + key[:12]
            db.execute(
                "INSERT OR IGNORE INTO refunds VALUES (?,?,?,?)",
                (payload["order_id"], key, payload["amount"], transaction),
            )
        return httpx.Response(
            200, json={"transaction_id": transaction, "amount": payload["amount"]}
        )


async def demo(workspace, scenario="approved", live=False):
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).parent
    spec = load_spec(root / "agent.yaml")
    service = OrderService(workspace / "orders.sqlite")
    tools = ToolRegistry()
    for raw in yaml.safe_load((root / "deployment.example.yaml").read_text())["tools"].values():
        tools.register(
            http_tool(
                HTTPToolConfig.model_validate({**raw, "auth_env": None}),
                transport=httpx.MockTransport(service.handle),
            )
        )
    proposal = {
        "reply": "Your order is eligible for review.",
        "refund": scenario != "answer",
        "amount": 49,
    }
    models = (
        make_models(spec)
        if live
        else {"main": MockProvider([ModelResponse(text=json.dumps(proposal))])}
    )
    runtime = Runtime(
        models, tools, journal=SQLiteJournal(workspace / "runs.sqlite"), allow_writes=True
    )
    result = await runtime.run(
        compile_agent(spec, root),
        {"order_id": "order-101", "question": "Please refund my unfulfilled order."},
    )
    if result.status == "waiting_input":
        runtime.journal.respond(
            result.run_id, result.waiting[0]["path"], {"approved": scenario == "approved"}
        )
        result = await Runtime(
            models, tools, journal=SQLiteJournal(workspace / "runs.sqlite"), allow_writes=True
        ).resume(result.run_id)
    if result.status != "succeeded":
        raise RuntimeError(result.error or result.status)
    with sqlite3.connect(service.path) as db:
        count = db.execute("SELECT COUNT(*) FROM refunds").fetchone()[0]
    report = {
        "mode": "live-model-fixture-service" if live else "offline-contract",
        "scenario": scenario,
        "status": result.status,
        "run_id": result.run_id,
        "output": result.output,
        "refunds": count,
    }
    (workspace / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--scenario", choices=["approved", "denied", "answer"], default="denied")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the configured model; order service remains a fixture.",
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(demo(args.workspace, args.scenario, args.live)), indent=2))
