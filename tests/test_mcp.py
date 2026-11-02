import asyncio
import socket

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from evosprig.core.protocols import ExecutionError
from evosprig.plugins.mcp_tools import MCPClient, MCPConnection, MCPToolConfig, mcp_tool


class SumResult(BaseModel):
    value: int


@pytest.fixture
async def endpoint():
    server = FastMCP("EvoSprig contract fixture", json_response=True, stateless_http=True)

    @server.tool()
    def add(a: int, b: int) -> SumResult:
        """Add two integers."""
        return SumResult(value=a + b)

    @server.resource("guide://runtime")
    def guide() -> str:
        return "Checkpoint completed work."

    @server.prompt()
    def explain(topic: str) -> str:
        return "Explain " + topic

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        server.streamable_http_app(),
        host="127.0.0.1",
        port=port,
        log_level="critical",
        access_log=False,
    )
    http_server = uvicorn.Server(config)
    task = asyncio.create_task(http_server.serve(sockets=[sock]))
    for _ in range(200):
        if http_server.started:
            break
        if task.done():
            await task
        await asyncio.sleep(0.01)
    assert http_server.started
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        http_server.should_exit = True
        await asyncio.wait_for(task, 10)
        sock.close()


async def test_real_mcp_http_handshake_tool_resource_prompt(endpoint):
    client = MCPClient(MCPConnection(endpoint=endpoint))
    manifest = await client.discover()
    assert manifest["protocol_version"] == "2025-11-25"
    assert manifest["server"]["name"] == "EvoSprig contract fixture"
    remote = manifest["tools"][0]
    config = MCPToolConfig(
        name="mcp.add",
        endpoint=endpoint,
        remote_name="add",
        description="Sum integers",
        input_schema=remote["inputSchema"],
        output_schema=remote["outputSchema"],
    )
    assert await mcp_tool(config).invoke({"a": 2, "b": 3}) == {"value": 5}
    resource = await client.read_resource("guide://runtime")
    assert resource["contents"][0]["text"] == "Checkpoint completed work."
    prompt = await client.get_prompt("explain", {"topic": "leases"})
    assert prompt["messages"][0]["content"]["text"] == "Explain leases"
    changed = config.model_copy(update={"input_schema": {"type": "object"}})
    with pytest.raises(ExecutionError, match="MCP session failed"):
        await mcp_tool(changed).invoke({"a": 2, "b": 3})


async def test_exported_mcp_workflow_runs_against_real_endpoint(endpoint, tmp_path):
    import json
    import os
    import sys

    from evosprig.core.version import compile_agent
    from evosprig.exporters.python import export_python
    from evosprig.sdk import Builder

    manifest = await MCPClient(MCPConnection(endpoint=endpoint)).discover()
    remote = manifest["tools"][0]
    binding = MCPToolConfig(
        name="mcp.add",
        endpoint=endpoint,
        remote_name="add",
        description="Sum",
        input_schema=remote["inputSchema"],
        output_schema=remote["outputSchema"],
    )
    spec = (
        Builder("portable-mcp", {"type": "object"}, remote["outputSchema"])
        .tool("sum", "mcp.add")
        .node(
            "sum",
            "tool",
            tool="sum",
            inputs={"a": {"value": 8}, "b": {"value": 5}},
            output_schema=remote["outputSchema"],
        )
        .output(value={"ref": "nodes.sum.output.value"})
        .build_spec()
    )
    destination = tmp_path / "export"
    report = export_python(
        compile_agent(spec), destination, tool_bindings={"mcp.add": binding.model_dump()}
    )
    assert report["external_tools"] == ["mcp.add"]
    assert "mcp==1.30.0" in (destination / "requirements.lock").read_text()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "app.py",
        "--mock",
        "--input",
        "{}",
        cwd=destination,
        env={**os.environ, "PYTHONPATH": str(destination / "src")},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), 20)
    assert process.returncode == 0, stderr.decode()
    assert json.loads(stdout)["output"] == {"value": 13}
