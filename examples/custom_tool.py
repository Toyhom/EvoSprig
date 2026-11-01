"""Register a tool from a separate module without changing the runtime."""

from evosprig.core.protocols import Tool, ToolRegistry


async def uppercase(text: str) -> dict:
    return {"text": text.upper()}


def register(registry: ToolRegistry):
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    }
    registry.register(
        Tool("example.uppercase", "Convert text to uppercase.", schema, schema, uppercase)
    )
