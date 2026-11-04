"""Expose the bounded JSON program interpreter as a tool."""

from evosprig.core.json_program import execute as execute
from evosprig.core.protocols import Tool


def python_tool():
    return Tool(
        "code.python",
        "Run a bounded Python transformation over JSON data.",
        {
            "type": "object",
            "properties": {
                "code": {"type": "string", "maxLength": 32000},
                "data": {"type": "object"},
                "max_value_chars": {"type": "integer", "minimum": 1024, "maximum": 8388608},
            },
            "required": ["code", "data"],
            "additionalProperties": False,
        },
        {},
        execute,
        pure=True,
    )
