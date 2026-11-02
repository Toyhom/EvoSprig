"""Explicit HTTP tool bindings; endpoints and credentials are not model arguments."""

from __future__ import annotations

import os
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator

from evosprig.core.protocols import ExecutionError, Tool, ToolFeedbackError
from evosprig.core.spec import Contract, canonical_json, check_schema
from evosprig.core.version import check_public_text


class HTTPToolConfig(Contract):
    kind: Literal["http"] = "http"
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2000)
    version: str = "1"
    endpoint: str
    method: Literal["GET", "POST", "PUT", "DELETE"] = "GET"
    input_schema: dict
    output_schema: dict
    auth_env: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    side_effect: Literal["read_only", "write"] = "read_only"
    idempotent: bool = False
    timeout_seconds: float = Field(default=15.0, gt=0, le=600)
    max_response_bytes: int = Field(default=2_000_000, ge=1, le=10_000_000)

    @model_validator(mode="after")
    def validate_contract(self):
        validate_endpoint(self.endpoint)
        check_schema(self.input_schema)
        check_schema(self.output_schema)
        check_public_text(canonical_json(self.model_dump()))
        if self.method in {"PUT", "DELETE"} and self.side_effect != "write":
            raise ValueError("PUT and DELETE require write permission")
        if self.idempotent and self.method == "GET":
            raise ValueError("GET tools do not need an idempotency key")
        return self


def validate_endpoint(endpoint):
    url = urlsplit(endpoint)
    if url.username or url.password or url.query or url.fragment or not url.hostname:
        raise ValueError("tool endpoint must not contain credentials, query or fragment")
    if url.scheme != "https" and not (
        url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        raise ValueError("tool endpoints require HTTPS or loopback HTTP")


def auth_headers(env):
    if not env:
        return {}
    value = os.environ.get(env)
    if not value:
        raise ExecutionError("tool authentication environment variable is missing")
    return {"Authorization": "Bearer " + value}


def http_tool(config: HTTPToolConfig, *, transport=None):
    async def invoke(**arguments):
        headers = auth_headers(config.auth_env)
        if config.idempotent:
            headers["Idempotency-Key"] = arguments.pop("idempotency_key")
        payload = {"params": arguments} if config.method == "GET" else {"json": arguments}
        if config.method == "GET" and any(
            isinstance(value, (dict, list)) for value in arguments.values()
        ):
            raise ExecutionError("HTTP GET tool arguments must be scalar query parameters")
        try:
            async with httpx.AsyncClient(
                transport=transport,
                timeout=config.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream(
                    config.method, config.endpoint, headers=headers, **payload
                ) as response:
                    if not 200 <= response.status_code < 300:
                        if config.side_effect == "read_only" and response.status_code in {400, 422}:
                            raise ToolFeedbackError(
                                "invalid_arguments",
                                "The read-only service rejected the arguments. Check the tool schema and revise the request.",
                            )
                        raise ExecutionError(f"HTTP tool returned status {response.status_code}")
                    content = bytearray()
                    async for part in response.aiter_bytes():
                        content.extend(part)
                        if len(content) > config.max_response_bytes:
                            raise ExecutionError("HTTP tool response exceeded its byte limit")
                    import json

                    try:
                        return json.loads(content)
                    except (ValueError, UnicodeError):
                        raise ExecutionError("HTTP tool returned invalid JSON") from None
        except httpx.TimeoutException:
            raise TimeoutError("HTTP tool request timed out") from None
        except httpx.HTTPError:
            raise OSError("HTTP tool transport failed") from None

    return Tool(
        config.name,
        config.description,
        config.input_schema,
        config.output_schema,
        invoke,
        version=config.version,
        side_effect=config.side_effect,
        idempotent=config.idempotent,
        timeout_seconds=config.timeout_seconds,
    )


def from_openapi(
    document, operation_id, *, base_url, name=None, auth_env=None, side_effect="read_only"
):
    """Import the portable static-path, JSON-body/query subset of OpenAPI 3.x.

    References, path templating, multipart and alternative authentication schemes
    require an explicit adapter; unsupported operations fail without approximation.
    """
    if not str(document.get("openapi", "")).startswith("3."):
        raise ValueError("OpenAPI 3.x is required")
    found = []
    for path, item in document.get("paths", {}).items():
        for method in ("get", "post", "put", "delete"):
            operation = item.get(method, {})
            if operation.get("operationId") == operation_id:
                found.append(
                    (
                        path,
                        method,
                        item.get("parameters", []) + operation.get("parameters", []),
                        operation,
                    )
                )
    if len(found) != 1:
        raise ValueError("operationId must identify exactly one operation")
    path, method, parameters, operation = found[0]
    if "{" in path or not path.startswith("/") or path.startswith("//"):
        raise ValueError("OpenAPI importer requires a static path")
    if "$ref" in canonical_json(operation):
        raise ValueError("resolve OpenAPI schema references before importing")
    if method == "get":
        if any(parameter.get("in") != "query" for parameter in parameters):
            raise ValueError("only query parameters are supported for GET")
        if any(
            parameter.get("schema", {}).get("type")
            not in {"string", "integer", "number", "boolean"}
            for parameter in parameters
        ):
            raise ValueError("GET query schemas must be scalar")
        input_schema = {
            "type": "object",
            "properties": {parameter["name"]: parameter["schema"] for parameter in parameters},
            "required": [
                parameter["name"] for parameter in parameters if parameter.get("required")
            ],
            "additionalProperties": False,
        }
    else:
        if parameters:
            raise ValueError("JSON body operations cannot also use parameters in this importer")
        input_schema = (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema")
        )
        if input_schema is None:
            raise ValueError("operation requires an application/json request schema")
    output_schema = (
        operation.get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if output_schema is None:
        raise ValueError("operation requires a 200 application/json response schema")
    return HTTPToolConfig(
        name=name or "http." + operation_id,
        description=operation.get("description") or operation.get("summary") or operation_id,
        endpoint=base_url.rstrip("/") + path,
        method=method.upper(),
        input_schema=input_schema,
        output_schema=output_schema,
        auth_env=auth_env,
        side_effect=side_effect,
    )
