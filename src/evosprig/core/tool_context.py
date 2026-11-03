"""Runtime identity supplied to tools independently of model arguments."""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCaller:
    run_id: str
    node_path: str
    mailbox: str | None = None


tool_caller: ContextVar[ToolCaller | None] = ContextVar("evosprig_tool_caller", default=None)


def caller():
    current = tool_caller.get()
    if current is None or current.mailbox is None:
        raise ValueError("messaging requires a runtime-bound agent mailbox")
    return current
