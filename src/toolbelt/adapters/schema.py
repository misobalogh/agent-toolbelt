"""Export the registry as tool definitions for different agent frameworks."""

from __future__ import annotations

from typing import Any, Literal

from toolbelt.core.registry import Registry, ToolSpec

SchemaFormat = Literal["openai"]


def export_schemas(registry: Registry, fmt: SchemaFormat) -> list[dict[str, Any]]:
    return [_to_openai(spec) for spec in registry.specs()]


def _to_openai(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.input_model.model_json_schema(),
        },
    }
