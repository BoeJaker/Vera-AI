#!/usr/bin/env python3
"""
Task registry for name-based task handler registration and execution
"""

from __future__ import annotations
from typing import Any, Callable, Dict


class TaskRegistry:
    """Name → handler registry for serializable tasks.
    handler(payload, context) -> Any
    """
    def __init__(self) -> None:
        self._h: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Any]] = {}

    def register(self, name: str):
        def deco(fn: Callable[[Dict[str, Any], Dict[str, Any]], Any]):
            self._h[name] = fn
            return fn
        return deco

    def run(self, name: str, payload: Dict[str, Any], context: Dict[str, Any]) -> Any:
        if name not in self._h:
            raise KeyError(f"No task handler registered for '{name}'")
        return self._h[name](payload, context)


GLOBAL_TASK_REGISTRY = TaskRegistry()