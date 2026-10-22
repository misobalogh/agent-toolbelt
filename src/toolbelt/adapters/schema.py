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


# Keys whose values are name -> schema maps, or plain data that must stay untouched.
_NAME_MAPS = {"properties", "$defs"}
_DATA_KEYS = {"default", "examples", "const", "enum"}


def _input_schema(spec: ToolSpec) -> dict[str, Any]:
    schema: dict[str, Any] = _strip_titles(spec.input_model.model_json_schema())
    return schema


def _strip_titles(node: Any) -> Any:
    """Drop the `title` keys pydantic adds to every field, they only cost tokens."""
    if isinstance(node, list):
        return [_strip_titles(item) for item in node]
    if not isinstance(node, dict):
        return node
    cleaned: dict[str, Any] = {}
    for key, value in node.items():
        if key == "title":
            continue
        if key in _NAME_MAPS and isinstance(value, dict):
            cleaned[key] = {name: _strip_titles(sub) for name, sub in value.items()}
        elif key in _DATA_KEYS:
            cleaned[key] = value
        else:
            cleaned[key] = _strip_titles(value)
    return cleaned


def _to_openai(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": _input_schema(spec),
        },
    }


def _to_anthropic(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "input_schema": _input_schema(spec),
    }


def _to_mcp(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": _input_schema(spec),
        "outputSchema": _strip_titles(spec.output_model.model_json_schema(mode="serialization")),
    }


_CONVERTERS: dict[str, Callable[[ToolSpec], dict[str, Any]]] = {
    "openai": _to_openai,
    "anthropic": _to_anthropic,
    "mcp": _to_mcp,
}
