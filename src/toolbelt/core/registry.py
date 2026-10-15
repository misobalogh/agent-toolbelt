"""Registry of tools, populated by the `tool` decorator."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel

from toolbelt.core.context import Context


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    func: Callable[[Any, Context], BaseModel]


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def tool[I: BaseModel, O: BaseModel](
        self, func: Callable[[I, Context], O]
    ) -> Callable[[I, Context], O]:
        """Register `func`. Models are taken from its type hints, the
        description from its docstring."""
        spec = _build_spec(func)
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec
        return func

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def specs(self) -> list[ToolSpec]:
        return [self._tools[name] for name in sorted(self._tools)]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


def _build_spec(func: Callable[..., Any]) -> ToolSpec:
    name = func.__name__
    description = inspect.getdoc(func)
    if not description:
        raise TypeError(f"tool {name} needs a docstring, it is the agent-facing description")
    params = list(inspect.signature(func).parameters)
    hints = get_type_hints(func)
    if len(params) != 2 or hints.get(params[1]) is not Context:
        raise TypeError(f"tool {name} must have the signature (args: InputModel, ctx: Context)")
    input_model = hints[params[0]]
    output_model = hints.get("return")
    for model in (input_model, output_model):
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            raise TypeError(f"tool {name} must take and return pydantic models")
    return ToolSpec(name, description, input_model, output_model, func)  # type: ignore[arg-type]


default_registry = Registry()
tool = default_registry.tool
