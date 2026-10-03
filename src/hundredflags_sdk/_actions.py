"""Dot-action calls share the named-call path and its fresh documentation checks."""

import keyword
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ._handles import TaskHandle
from .models import JsonObject, TaskDocumentation


def _dot_name(name: str) -> bool:
    return name.isidentifier() and not name.startswith("_") and not keyword.iskeyword(name)


class ActionMethods[TaskT: TaskHandle, ResultT](ABC):
    def __init__(self, task: TaskT) -> None:
        self._task = task

    @abstractmethod
    def call(self, name: str, arguments: JsonObject) -> ResultT:
        """Validate against fresh public documentation before invoking an action."""
        ...

    def __getattr__(self, name: str) -> Callable[..., ResultT]:
        if not _dot_name(name):
            raise AttributeError(name)

        def invoke(**arguments: Any) -> ResultT:
            return self.call(name, arguments)

        return invoke

    def __dir__(self) -> list[str]:
        names = set(super().__dir__())
        info = self._task.info
        if isinstance(info, TaskDocumentation):
            names.update(action.name for action in info.actions if _dot_name(action.name))
        return sorted(names)
