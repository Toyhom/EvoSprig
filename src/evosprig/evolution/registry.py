"""Trusted optimizer plugins share EvoSprig evaluation and release handling."""

from __future__ import annotations

import inspect
import re
import threading
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Awaitable, Callable

from .methods import METHODS


@dataclass(frozen=True)
class Optimizer:
    name: str
    optimize: Callable[..., Awaitable[dict]]
    title: str
    family: str
    feedback: str
    source: str = ""


_PLUGINS: dict[str, Optimizer] = {}
_LOADED = False
_LOCK = threading.RLock()


def register_method(name, optimize, *, title, family, feedback, source=""):
    """Register async optimize(context, *, config) once at application startup."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name):
        raise ValueError("method name must be a lowercase identifier")
    if name in METHODS or name in _PLUGINS:
        raise ValueError(f"method already registered: {name}")
    if not inspect.iscoroutinefunction(optimize):
        raise TypeError("optimizer must be an async function")
    if not all(isinstance(value, str) and value.strip() for value in (title, family, feedback)):
        raise ValueError("method title, family and feedback are required")
    _PLUGINS[name] = Optimizer(name, optimize, title, family, feedback, source)
    METHODS[name] = {"name": title, "family": family, "feedback": feedback, "source": source}


def load_methods():
    """Load installed package entry points; task inputs never supply import paths."""
    global _LOADED
    with _LOCK:
        if not _LOADED:
            methods, plugins = dict(METHODS), dict(_PLUGINS)
            try:
                for entry in entry_points(group="evosprig.evolution"):
                    entry.load()()
            except Exception:
                # A failed installation can be retried without duplicate registrations.
                METHODS.clear()
                METHODS.update(methods)
                _PLUGINS.clear()
                _PLUGINS.update(plugins)
                raise
            _LOADED = True


def require_method(name):
    load_methods()
    if name not in METHODS:
        raise ValueError(f"unknown evolution method: {name}")
    return name


def custom_method(name):
    require_method(name)
    return _PLUGINS.get(name)
