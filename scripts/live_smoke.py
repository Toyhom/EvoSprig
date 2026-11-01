"""Opt-in paid verification: six calls, no retries, at most 704 generated tokens."""

import argparse
import asyncio
import getpass
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from evosprig.core.protocols import ModelRequest
from evosprig.core.runtime import Runtime
from evosprig.core.spec import load_spec
from evosprig.core.version import compile_agent
from evosprig.plugins.builtin_tools import builtin_registry
from evosprig.plugins.openai_compatible import Connection, OpenAICompatibleProvider


async def verify(report):
    connection = Connection(
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key_env="DEEPSEEK_API_KEY",
        options={"thinking": {"type": "disabled"}},
    )
    provider = OpenAICompatibleProvider(connection)
    report["connection"] = connection.model_dump()

    async def call(name, messages, limit, **kwargs):
        started = time.monotonic()
        response = await provider.complete(
            ModelRequest(messages, max_output_tokens=limit, **kwargs)
        )
        report["checks"].append(
            {
                "name": name,
                "model": response.model,
                "usage": asdict(response.usage),
                "seconds": round(time.monotonic() - started, 3),
            }
        )
        return response

    text = await call("text", [{"role": "user", "content": "Reply with exactly EVO_OK."}], 64)
    assert text.text.strip() == "EVO_OK", "unexpected text response"
    report["checks"][-1]["passed"] = True
    structured = await call(
        "structured_output",
        [{"role": "user", "content": 'Return only the JSON object {"answer":42}.'}],
        128,
        json_output=True,
    )
    assert json.loads(structured.text) == {"answer": 42}, "unexpected JSON response"
    report["checks"][-1]["passed"] = True
    tools = builtin_registry()
    tool = tools.resolve("builtin.add")
    messages = [
        {
            "role": "system",
            "content": "Use the add tool to calculate. After observing the tool result, reply with only the number.",
        },
        {"role": "user", "content": "Use add to calculate 19 + 23."},
    ]
    first = await call("tool_call", messages, 128, tools=[tool.descriptor("add")])
    assert len(first.tool_calls) == 1 and first.tool_calls[0].name == "add", "expected one add call"
    invocation = first.tool_calls[0]
    observation = await tool.invoke(invocation.arguments)
    assert observation == {"value": 42}, "unexpected tool result"
    report["checks"][-1]["passed"] = True
    messages += [
        {
            "role": "assistant",
            "content": first.text or None,
            "tool_calls": [
                {
                    "id": invocation.id,
                    "type": "function",
                    "function": {
                        "name": invocation.name,
                        "arguments": json.dumps(invocation.arguments),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": invocation.id, "content": json.dumps(observation)},
    ]
    final = await call("tool_observation", messages, 64, tools=[tool.descriptor("add")])
    assert final.text.strip() == "42", "unexpected final answer"
    report["checks"][-1]["passed"] = True
    chunks = [
        chunk
        async for chunk in provider.stream(
            ModelRequest(
                [{"role": "user", "content": "Reply with exactly STREAM_OK."}], max_output_tokens=64
            )
        )
    ]
    assert "".join(chunk.get("text", "") for chunk in chunks).strip() == "STREAM_OK", (
        "unexpected stream"
    )
    usages = [chunk["usage"] for chunk in chunks if chunk["type"] == "usage"]
    assert usages, "stream did not report usage"
    report["checks"].append(
        {
            "name": "stream",
            "passed": True,
            "usage": {
                "input_tokens": usages[-1]["prompt_tokens"],
                "output_tokens": usages[-1]["completion_tokens"],
            },
        }
    )
    root = Path(__file__).resolve().parents[1] / "examples/hello"
    spec = load_spec(root / "agent.yaml")
    result = await Runtime({"main-model": provider}, tools).run(
        compile_agent(spec, root), {"question": "What is 2 + 3? Reply with exactly the number 5."}
    )
    assert result.status == "succeeded" and result.output["answer"].strip() == "5", (
        "runtime verification failed"
    )
    report["checks"].append(
        {
            "name": "runtime",
            "passed": True,
            "agent_version": result.agent_version,
            "usage": result.usage,
            "event_count": len(result.events),
        }
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--prompt-key", action="store_true", help="Read a hidden key without saving it"
    )
    args = parser.parse_args()
    if args.prompt_key:
        os.environ["DEEPSEEK_API_KEY"] = getpass.getpass("API key (hidden): ")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("Set DEEPSEEK_API_KEY or pass --prompt-key")
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": [],
        "budget": {"max_requests": 6, "max_output_tokens": 704, "retries": 0},
        "cost": None,
        "cost_note": "Token usage is measured; monetary cost requires provider billing reconciliation.",
    }
    try:
        asyncio.run(verify(report))
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = {"type": type(exc).__name__, "code": getattr(exc, "code", "verification")}
    finally:
        report["total_usage"] = {
            key: sum(check.get("usage", {}).get(key, 0) for check in report["checks"])
            for key in ("input_tokens", "output_tokens")
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "checks": len(report["checks"]),
                "usage": report["total_usage"],
            }
        )
    )
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
