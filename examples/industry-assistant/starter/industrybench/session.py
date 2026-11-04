"""An isolated application record with read/decide tools and operation receipts."""

import json
from copy import deepcopy

from .registry import CASES


class Session:
    def __init__(self, case_id):
        self.case = next((dict(case) for case in CASES if case["id"] == case_id), None)
        if self.case is None:
            raise ValueError("Unknown training-grant case")
        self.industry = "government"
        self.env = self
        self.state = {"application": dict(self.case), "decision": None, "reason": ""}
        self.receipts = {}
        self.read = False

    def observation(self):
        return {"case_id": self.case["id"], "request": "Process this training-grant application."}

    def search(self, query, limit=8):
        tools = [
            {"name": "application.read", "description": "Read the application and saved decision",
             "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "application.decide", "description": "Record a decision after reading the case",
             "parameters": {"type": "object", "properties": {
                 "decision": {"enum": ["approve", "deny", "request_documents", "manual_review"]},
                 "reason": {"type": "string", "minLength": 1}},
                 "required": ["decision", "reason"], "additionalProperties": False}},
        ]
        return [{"type": "function", "function": tool} for tool in tools][:limit]

    def call(self, name, arguments, idempotency_key=None):
        signature = json.dumps([name, arguments], sort_keys=True)
        if not idempotency_key:
            return {"ok": False, "error": "An operation key is required"}
        if idempotency_key in self.receipts:
            previous, result = self.receipts[idempotency_key]
            return deepcopy(result) if previous == signature else {"ok": False, "error": "Key conflict"}
        if name == "application.read" and arguments == {}:
            self.read = True
            result = {"ok": True, **deepcopy(self.state)}
        elif name == "application.decide":
            if not self.read:
                return {"ok": False, "error": "Read the application first"}
            if (set(arguments) != {"decision", "reason"}
                    or arguments["decision"] not in {
                        "approve", "deny", "request_documents", "manual_review"}
                    or not isinstance(arguments["reason"], str) or not arguments["reason"].strip()):
                return {"ok": False, "error": "Provide a valid decision and reason"}
            self.state.update(arguments)
            result = {"ok": True, **deepcopy(self.state)}
        else:
            return {"ok": False, "error": "Unknown tool or invalid arguments"}
        self.receipts[idempotency_key] = (signature, deepcopy(result))
        return result

    def final_state(self):
        return deepcopy(self.state)

    def close(self):
        pass
