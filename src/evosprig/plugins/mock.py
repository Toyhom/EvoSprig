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
        text = "Mock: " + request.messages[-1]["content"]
        if request.json_output:
            text = json.dumps({"answer": "mock"})
        return ModelResponse(text=text, model=self.model_id, usage=Usage(8, 8))
