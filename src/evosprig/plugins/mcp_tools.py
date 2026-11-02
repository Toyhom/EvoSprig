"""MCP 1.30 SDK adapter for the tested 2025-11-25 Streamable HTTP subset."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal

import httpx
from pydantic import Field, model_validator

from evosprig.core.protocols import ExecutionError, Tool
from evosprig.core.spec import Contract, canonical_json, check_schema
from evosprig.core.version import check_public_text

from .http_tools import auth_headers, validate_endpoint


class MCPConnection(Contract):
    endpoint: str
    auth_env: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    protocol_version: Literal["2025-11-25"] = "2025-11-25"
    timeout_seconds: float = Field(default=20.0, gt=0, le=600)
    max_response_bytes: int = Field(default=2_000_000, ge=1, le=10_000_000)

    @model_validator(mode="after")
    def validate_connection(self):
        validate_endpoint(self.endpoint)
        check_public_text(canonical_json(self.model_dump()))
        return self


class MCPToolConfig(MCPConnection):
    kind: Literal["mcp"] = "mcp"
    name: str = Field(min_length=1, max_length=128)
    remote_name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2000)
    version: str = "1"
    input_schema: dict
    output_schema: dict
    side_effect: Literal["read_only", "write"] = "read_only"
    result_format: Literal["structured", "content"] = "structured"

    @model_validator(mode="after")
    def validate_schemas(self):
        check_schema(self.input_schema)
        check_schema(self.output_schema)
        return self


class MCPClient:
    """Scoped sessions; no sampling, elicitation, roots or task capability is advertised."""

    def __init__(self, connection: MCPConnection, *, transport=None):
        self.connection, self.transport = connection, transport
        self.last_handshake = None

    @asynccontextmanager
    async def session(self):
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            raise ExecutionError("install evosprig[mcp] for MCP connections") from None
        config = self.connection
        try:
            async with httpx.AsyncClient(
                headers=auth_headers(config.auth_env),
                timeout=config.timeout_seconds,
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                async with streamable_http_client(config.endpoint, http_client=client) as (
                    read,
                    write,
                    _,
                ):
                    async with ClientSession(
                        read, write, read_timeout_seconds=timedelta(seconds=config.timeout_seconds)
                    ) as session:
                        handshake = await session.initialize()
                        if handshake.protocolVersion != config.protocol_version:
                            raise ExecutionError(
                                "MCP protocol version differs from the pinned version"
                            )
                        self.last_handshake = {
                            "protocol_version": handshake.protocolVersion,
                            "server": handshake.serverInfo.model_dump(mode="json"),
                            "capabilities": handshake.capabilities.model_dump(
                                mode="json", exclude_none=True
                            ),
                        }
                        yield session
        except Exception:
            # Exception groups and upstream messages may contain credential-bearing content.
            raise ExecutionError(
                "MCP session failed; verify endpoint, protocol and remote contract"
            ) from None

    def _bounded(self, value):
        if len(canonical_json(value).encode()) > self.connection.max_response_bytes:
            raise ExecutionError("MCP response exceeds its configured byte limit")
        return value

    async def discover(self):
        async with self.session() as session:
            tools, cursor, seen = [], None, set()
            for _ in range(100):
                page = await session.list_tools(cursor=cursor)
                tools.extend(item.model_dump(mode="json", exclude_none=True) for item in page.tools)
                cursor = page.nextCursor
                if not cursor:
                    break
                if cursor in seen:
                    raise ExecutionError("MCP pagination repeated its cursor")
                seen.add(cursor)
            else:
                raise ExecutionError("MCP tool discovery exceeded its page limit")
        return self._bounded({**self.last_handshake, "tools": tools})

    async def read_resource(self, uri):
        from pydantic import AnyUrl

        async with self.session() as session:
            result = await session.read_resource(AnyUrl(uri))
        return self._bounded(result.model_dump(mode="json", exclude_none=True))

    async def get_prompt(self, name, arguments=None):
        async with self.session() as session:
            result = await session.get_prompt(name, arguments)
        return self._bounded(result.model_dump(mode="json", exclude_none=True))

    async def call(self, config: MCPToolConfig, arguments):
        async with self.session() as session:
            cursor, remote = None, None
            for _ in range(100):
                page = await session.list_tools(cursor=cursor)
                remote = next(
                    (tool for tool in page.tools if tool.name == config.remote_name), None
                )
                if remote is not None or not page.nextCursor:
                    break
                cursor = page.nextCursor
            if remote is None or remote.inputSchema != config.input_schema:
                raise ExecutionError("MCP input schema changed")
            if config.result_format == "structured" and remote.outputSchema != config.output_schema:
                raise ExecutionError("MCP output schema changed")
            result = await session.call_tool(config.remote_name, arguments)
        if result.isError:
            raise ExecutionError("MCP tool returned an error")
        if config.result_format == "structured":
            if result.structuredContent is None:
                raise ExecutionError("MCP tool omitted structured content")
            return self._bounded(result.structuredContent)
        return self._bounded(
            {
                "content": [
                    item.model_dump(mode="json", exclude_none=True) for item in result.content
                ]
            }
        )


def mcp_tool(config: MCPToolConfig, *, transport=None):
    client = MCPClient(config, transport=transport)

    async def invoke(**arguments):
        return await client.call(config, arguments)

    return Tool(
        config.name,
        config.description,
        config.input_schema,
        config.output_schema,
        invoke,
        version=config.version,
        side_effect=config.side_effect,
        timeout_seconds=config.timeout_seconds,
    )
