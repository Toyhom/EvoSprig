"""Local order service for trying the customer-support application."""

import argparse
import json
import os
import secrets
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


class Refund(BaseModel):
    order_id: str
    amount: float = Field(gt=0, allow_inf_nan=False)


def create_app(database, token):
    if not token:
        raise ValueError("Set SUPPORT_API_TOKEN")
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS orders
                (id TEXT PRIMARY KEY, total REAL, status TEXT, refunded INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS receipts
                (key TEXT PRIMARY KEY, request TEXT, response TEXT);
            INSERT OR IGNORE INTO orders(id,total,status) VALUES ('ORDER-1001',49.0,'unfulfilled');
            INSERT OR IGNORE INTO orders(id,total,status) VALUES ('ORDER-1002',75.0,'delivered');
        """)
    app = FastAPI()

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        from fastapi.responses import JSONResponse
        if not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return await call_next(request)

    @app.get("/lookup")
    def lookup(order_id: str):
        with sqlite3.connect(database) as db:
            row = db.execute("SELECT total,status,refunded FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Order not found")
        return {"order_id": order_id, "total": row[0], "status": row[1], "paid": True,
                "within_policy_window": True, "refunded": bool(row[2])}

    @app.post("/refund")
    def refund(payload: Refund, request: Request):
        key = request.headers.get("idempotency-key")
        if not key:
            raise HTTPException(400, "Idempotency-Key required")
        signature = json.dumps(payload.model_dump(), sort_keys=True)
        with sqlite3.connect(database) as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT request,response FROM receipts WHERE key=?", (key,)).fetchone()
            if old:
                if old[0] != signature:
                    raise HTTPException(409, "Operation key was used with different arguments")
                return json.loads(old[1])
            row = db.execute("SELECT total,status,refunded FROM orders WHERE id=?", (payload.order_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Order not found")
            if row[1] != "unfulfilled" or row[2] or payload.amount != row[0]:
                raise HTTPException(409, "Only an unfulfilled, unrefunded order's full amount is eligible")
            result = {"transaction_id": secrets.token_hex(12), "amount": payload.amount}
            db.execute("UPDATE orders SET refunded=1 WHERE id=?", (payload.order_id,))
            db.execute("INSERT INTO receipts VALUES (?,?,?)", (key, signature, json.dumps(result)))
            return result

    return app


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path(".evosprig/support-store.sqlite"))
    parser.add_argument("--port", type=int, default=18881)
    args = parser.parse_args()
    uvicorn.run(create_app(args.database, os.environ.get("SUPPORT_API_TOKEN")), host="127.0.0.1", port=args.port)
