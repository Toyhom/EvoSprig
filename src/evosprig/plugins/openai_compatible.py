"""OpenAI-compatible chat adapter, with bounded requests and sanitized errors."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator

from evosprig.core.protocols import ModelRequest, ModelResponse, ProviderError, ToolCall, Usage
from evosprig.core.spec import Contract


class Connection(Contract):
    base_url: str
    model: str
    api_key_env: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    timeout_seconds: float = Field(default=45.0, gt=0, le=600)
    capabilities: list[str] = Field(
        default_factory=lambda: ["text", "tool_calling", "structured_output"]
    )
    options: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_endpoint(self):
        url = urlsplit(self.base_url)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ValueError("base_url must be an endpoint without credentials, query or fragment")
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("use HTTPS, or HTTP for a loopback inference service")
        if set(self.options) - {"thinking", "reasoning_effort", "chat_template_kwargs"}:
            raise ValueError("unsupported provider option")
        template = self.options.get("chat_template_kwargs")
        if template is not None and (
            not isinstance(template, dict)
            or set(template) != {"enable_thinking"}
            or not isinstance(template["enable_thinking"], bool)
        ):
            raise ValueError("chat_template_kwargs supports only boolean enable_thinking")
        return self


class OpenAICompatibleProvider:
    def __init__(
        self, connection: Connection, *, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.connection = connection
        self.model_id = connection.model
        self.capabilities = frozenset(connection.capabilities)
        self.transport = transport

    def _key(self) -> str:
        key = os.environ.get(self.connection.api_key_env)
        if not key:
            raise ProviderError(
                "configuration", f"missing environment variable {self.connection.api_key_env}"
            )
        return key

    def _payload(self, request: ModelRequest, stream: bool = False) -> dict:
        payload = {
            "model": self.model_id,
            "messages": request.messages,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "stream": stream,
            **self.connection.options,
        }
        if request.tools:
            payload["tools"] = request.tools
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.json_output:
            payload["response_format"] = {"type": "json_object"}
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.connection.timeout_seconds,
            transport=self.transport,
            follow_redirects=False,
            trust_env=False,
        )

    @property
    def endpoint(self) -> str:
        return self.connection.base_url.rstrip("/") + "/chat/completions"

    @staticmethod
    def _check_status(response: httpx.Response):
        if response.status_code >= 300:
            status = response.status_code
            code = (
                "authentication"
                if status in (401, 403)
                else "rate_limit"
                if status == 429
                else "upstream"
            )
            raise ProviderError(code, f"model endpoint returned HTTP {status}")

    @staticmethod
    def _parse(body: dict) -> ModelResponse:
        try:
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("output_limit", "model response reached its output limit")
            if choice.get("finish_reason") == "content_filter":
                raise ProviderError("content_filter", "provider filtered the response")
            message = choice["message"]
            calls = []
            for call in message.get("tool_calls") or []:
                arguments = json.loads(call["function"]["arguments"])
                if not isinstance(arguments, dict) or not call["id"]:
                    raise ValueError("invalid tool call")
                calls.append(ToolCall(call["id"], call["function"]["name"], arguments))
            usage = body["usage"]
            return ModelResponse(
                text=message.get("content") or "",
                tool_calls=tuple(calls),
                usage=Usage(int(usage["prompt_tokens"]), int(usage["completion_tokens"])),
                model=body.get("model", "unknown"),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError(
                "invalid_response", "model response did not satisfy the chat contract"
            ) from exc

    async def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            async with self._client() as client:
                response = await client.post(
                    self.endpoint,
                    json=self._payload(request),
                    headers={"Authorization": "Bearer " + self._key()},
                )
                self._check_status(response)
                return self._parse(response.json())
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "model request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network", "model transport failed") from exc
        except (ValueError, TypeError) as exc:
            raise ProviderError("invalid_response", "model response was not valid JSON") from exc

    async def stream(self, request: ModelRequest) -> AsyncIterator[dict]:
        """Yield public text/tool deltas and usage, excluding private reasoning fields."""
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST",
                    self.endpoint,
                    json=self._payload(request, True),
                    headers={"Authorization": "Bearer " + self._key()},
                ) as response:
                    self._check_status(response)
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        body = json.loads(data)
                        if body.get("usage"):
                            yield {
                                "type": "usage",
                                "usage": {
                                    key: body["usage"].get(key, 0)
                                    for key in (
                                        "prompt_tokens",
                                        "completion_tokens",
                                        "total_tokens",
                                    )
                                },
                            }
                        for choice in body.get("choices", []):
                            if choice.get("finish_reason") == "length":
                                raise ProviderError(
                                    "output_limit", "model stream reached its output limit"
                                )
                            delta = choice.get("delta", {})
                            if delta.get("content"):
                                yield {"type": "text", "text": delta["content"]}
                            if delta.get("tool_calls"):
                                yield {"type": "tool_delta", "tool_calls": delta["tool_calls"]}
                    raise ProviderError(
                        "incomplete_stream", "model stream ended without a completion marker"
                    )
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "model stream timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network", "model stream transport failed") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("invalid_response", "model stream contained invalid data") from exc
