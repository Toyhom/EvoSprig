"""Deterministic offline provider; reports mock identity in every response."""

import json
from collections import deque

from evosprig.core.protocols import ModelRequest, ModelResponse, Usage


class MockProvider:
    capabilities = frozenset({"text", "tool_calling", "structured_output"})
    model_id = "mock/offline"

    def __init__(self, responses: list[ModelResponse] | None = None):
        self.responses = deque(responses or [])
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.responses:
            return self.responses.popleft()
        if request.json_output and request.messages[0]["content"].startswith(
            "Optimize the editable instruction texts"
        ):
            payload = json.loads(request.messages[-1]["content"])
            history = payload.get("history", [])
            previous = history[-1]["resources"] if history else {}
            text = json.dumps(
                {
                    name: previous.get(name, "Answer clearly.")
                    + "\nMock proposal: keep the answer concise."
                    for name in payload["editable_resources"]
                }
            )
            return ModelResponse(text=text, model=self.model_id, usage=Usage(8, 8))
        if request.messages[0]["content"].startswith(
            "I provided an assistant with the following instructions"
        ):
            return ModelResponse(
                text="```\nMock proposal: answer clearly and concisely.\n```",
                model=self.model_id,
                usage=Usage(8, 8),
            )
        if request.messages[0]["content"].startswith("You are an independent task evaluator"):
            return ModelResponse(
                text=json.dumps(
                    {
                        "score": 0.5,
                        "feedback": "Offline judge placeholder",
                        "confidence": 0.0,
                        "evidence": [],
                        "limitations": "No model quality assessment in mock mode",
                    }
                ),
                model=self.model_id,
                usage=Usage(8, 8),
            )
        text = "Mock: " + request.messages[-1]["content"]
        if request.json_output:
            text = json.dumps({"answer": "mock"})
        return ModelResponse(text=text, model=self.model_id, usage=Usage(8, 8))
