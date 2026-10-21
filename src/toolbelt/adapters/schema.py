"""Export the registry as tool definitions for different agent frameworks."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, get_args

from toolbelt.core.registry import Registry, ToolSpec

SchemaFormat = Literal["openai", "anthropic", "mcp"]
FORMATS: tuple[str, ...] = get_args(SchemaFormat)


def export_schemas(registry: Registry, fmt: SchemaFormat) -> list[dict[str, Any]]:
    convert = _CONVERTERS[fmt]
    return [convert(spec) for spec in registry.specs()]


def _to_openai(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.input_model.model_json_schema(),
        },
    }


def _to_anthropic(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "input_schema": spec.input_model.model_json_schema(),
    }


def _to_mcp(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": spec.input_model.model_json_schema(),
        "outputSchema": spec.output_model.model_json_schema(mode="serialization"),
    }


_CONVERTERS: dict[str, Callable[[ToolSpec], dict[str, Any]]] = {
    "openai": _to_openai,
    "anthropic": _to_anthropic,
    "mcp": _to_mcp,
}
