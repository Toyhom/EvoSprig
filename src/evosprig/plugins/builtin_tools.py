from evosprig.core.protocols import Tool, ToolRegistry


def text_stats(text: str) -> dict:
    return {"characters": len(text), "words": len(text.split())}


def add(a: float, b: float) -> dict:
    return {"value": a + b}


BUILTIN_NAMES = frozenset({"builtin.text_stats", "builtin.add"})


def builtin_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            "builtin.text_stats",
            "Count characters and whitespace-separated words.",
            {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {"characters": {"type": "integer"}, "words": {"type": "integer"}},
                "required": ["characters", "words"],
                "additionalProperties": False,
            },
            text_stats,
        )
    )
    registry.register(
        Tool(
            "builtin.add",
            "Add two numbers.",
            {
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
                "additionalProperties": False,
            },
            {
                "type": "object",
                "properties": {"value": {"type": "number"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            add,
        )
    )
    return registry
