"""Registry of tools, populated by the `tool` decorator."""

from __future__ import annotations

import difflib
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel, ValidationError

from toolbelt.core.context import Context
from toolbelt.core.errors import ErrorCode, InvalidInput, ToolError, UnknownTool
from toolbelt.core.limits import Deadline, Limits
from toolbelt.core.sandbox import Sandbox


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
        try:
            return self._tools[name]
        except KeyError:
            close = difflib.get_close_matches(name, self._tools, n=3)
            hint = f"did you mean: {', '.join(close)}" if close else "list the available tools"
            raise UnknownTool(f"unknown tool: {name}", hint=hint) from None

    def call(
        self,
        name: str,
        arguments: dict[str, Any],
        sandbox: Sandbox,
        limits: Limits | None = None,
    ) -> BaseModel:
        """Validate `arguments`, run the tool and return its output model.

        Only ToolError escapes. Anything else a tool raises is a bug in the
        tool, reported as an internal error instead of crashing the caller.
        """
        spec = self.get(name)
        try:
            args = spec.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise InvalidInput(_summarize(exc), hint=f"check the input schema of {name}") from exc
        limits = limits or Limits()
        ctx = Context(sandbox, limits, Deadline(limits.timeout_s))
        try:
            return spec.func(args, ctx)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(
                f"{name} failed unexpectedly: {type(exc).__name__}",
                hint="this is a bug in the tool, not in your input",
                code=ErrorCode.INTERNAL,
            ) from exc

    def specs(self) -> list[ToolSpec]:
        return [self._tools[name] for name in sorted(self._tools)]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


def _summarize(exc: ValidationError) -> str:
    parts = [f"{'.'.join(str(p) for p in e['loc']) or 'input'}: {e['msg']}" for e in exc.errors()]
    return "invalid input: " + "; ".join(parts)


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
