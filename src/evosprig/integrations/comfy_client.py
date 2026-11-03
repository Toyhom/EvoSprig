"""Async ComfyUI API client; submission and GPU waiting are separate operations."""

from __future__ import annotations

import json
import re

import httpx

from evosprig.core.protocols import ToolRejectedError
from evosprig.plugins.http_tools import auth_headers, validate_endpoint


class ComfyValidationError(ToolRejectedError):
    """The server rejected a prompt before adding it to the render queue."""

    def __init__(self, message):
        super().__init__("comfy_validation", message)


def validation_message(payload):
    from evosprig.core.version import SECRET

    messages = []
    error = payload.get("error", {})
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        messages.append(error["message"][:300])
    nodes = payload.get("node_errors", {})
    for node_id, node in list(nodes.items())[:8] if isinstance(nodes, dict) else []:
        if not isinstance(node, dict):
            continue
        for error in node.get("errors", [])[:3]:
            if isinstance(error, dict):
                detail = ": ".join(error[key][:300] for key in ("message", "details")
                                   if isinstance(error.get(key), str) and error[key])
                if detail:
                    messages.append(f"Node {node_id} ({node.get('class_type', 'unknown')}): {detail}")
    return SECRET.sub("[redacted]", "ComfyUI rejected the graph: " + "; ".join(messages))[:2000]


class ComfyClient:
    def __init__(self, base_url="http://127.0.0.1:8188", *, auth_env=None, dedicated=False,
                 transport=None, timeout=30, max_bytes=64_000_000):
        validate_endpoint(base_url)
        self.base_url = base_url.rstrip("/")
        self.auth_env, self.dedicated = auth_env, dedicated
        self.transport, self.timeout, self.max_bytes = transport, timeout, max_bytes

    async def request(self, method, path, **kwargs):
        async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False,
                                     timeout=self.timeout) as client:
            async with client.stream(method, self.base_url + path, headers=auth_headers(self.auth_env), **kwargs) as response:
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > self.max_bytes:
                        raise ValueError("ComfyUI response exceeds the configured limit")
                if response.status_code == 400 and method == "POST" and path == "/prompt":
                    try:
                        rejected = json.loads(raw)
                    except (ValueError, UnicodeError):
                        rejected = None
                    # Only a structured, explicit rejection is definitive. A
                    # timeout, proxy error or malformed response stays uncertain.
                    if (isinstance(rejected, dict) and isinstance(rejected.get("error"), dict)
                            and rejected["error"].get("type") and "node_errors" in rejected
                            and not rejected.get("prompt_id")):
                        raise ComfyValidationError(validation_message(rejected))
                response.raise_for_status()
                return json.loads(raw) if raw else {}

    async def object_info(self):
        return await self.request("GET", "/object_info")

    async def submit(self, prompt, *, client_id, operation_id=None):
        # ComfyUI's POST /prompt has no idempotency guarantee. Callers must journal
        # an uncertain response and reconcile the queue/history before resubmitting.
        body = {"prompt": prompt, "client_id": client_id}
        if operation_id:
            body["extra_data"] = {"evosprig_operation": operation_id}
        result = await self.request("POST", "/prompt", json=body)
        # ComfyUI can accept valid output branches and report errors for other
        # branches in the same response. Always retain an accepted prompt ID.
        if not result.get("prompt_id"):
            raise ValueError("ComfyUI returned no prompt ID; reconcile the queue before retrying")
        return self.prompt_id(result["prompt_id"])

    @staticmethod
    def prompt_id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise ValueError("invalid ComfyUI prompt ID")
        return value

    async def status(self, prompt_id):
        prompt_id = self.prompt_id(prompt_id)
        history = await self.request("GET", "/history/" + prompt_id)
        if prompt_id in history:
            record = history[prompt_id]
            status = record.get("status", {})
            if status.get("status_str") == "error":
                return {"status": "failed", "error": status.get("messages", []), "output": record.get("outputs", {})}
            if status.get("completed"):
                return {"status": "succeeded", "output": record.get("outputs", {})}
        queue = await self.request("GET", "/queue")
        for field, state in (("queue_running", "running"), ("queue_pending", "queued")):
            if any(row[1] == prompt_id for row in queue.get(field, [])):
                return {"status": state}
        # Completion can occur between the history and queue reads.
        history = await self.request("GET", "/history/" + prompt_id)
        if prompt_id in history and history[prompt_id].get("status", {}).get("completed"):
            record = history[prompt_id]
            failed = record.get("status", {}).get("status_str") == "error"
            return {"status": "failed" if failed else "succeeded", "output": record.get("outputs", {}),
                    **({"error": record["status"].get("messages", [])} if failed else {})}
        return {"status": "unknown"}

    async def find_operation(self, operation_id):
        queue = await self.request("GET", "/queue")
        history = await self.request("GET", "/history")
        rows = queue.get("queue_running", []) + queue.get("queue_pending", [])
        rows += [value["prompt"] for value in history.values() if "prompt" in value]
        ids = {row[1] for row in rows if len(row) > 3 and isinstance(row[3], dict)
               and row[3].get("evosprig_operation") == operation_id}
        if len(ids) > 1:
            raise ValueError("multiple ComfyUI prompts match this operation")
        return next(iter(ids), None)

    async def cancel(self, prompt_id):
        prompt_id = self.prompt_id(prompt_id)
        queue = await self.request("GET", "/queue")
        if any(row[1] == prompt_id for row in queue.get("queue_running", [])):
            if not self.dedicated:
                raise ValueError("running-job interruption requires a dedicated ComfyUI instance")
            await self.request("POST", "/interrupt", json={"prompt_id": prompt_id})
        else:
            await self.request("POST", "/queue", json={"delete": [prompt_id]})

    async def free_models(self):
        if not self.dedicated:
            raise ValueError("model unloading requires a dedicated ComfyUI instance")
        queue = await self.request("GET", "/queue")
        if queue.get("queue_running") or queue.get("queue_pending"):
            raise ValueError("finish or cancel pending work before unloading models")
        return await self.request("POST", "/free", json={"unload_models": True, "free_memory": True})
