from collections.abc import Callable
from typing import Any

import pytest
from pydantic import Field
from sample_tools import make_sample_registry

from toolbelt.adapters.schema import FORMATS, SchemaFormat, export_schemas
from toolbelt.core.context import Context
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import Registry


@pytest.mark.parametrize("fmt", FORMATS)
def test_export_matches_snapshot(
    fmt: SchemaFormat, assert_snapshot: Callable[[str, Any], None]
) -> None:
    assert_snapshot(f"sample_{fmt}", export_schemas(make_sample_registry(), fmt))


def test_openai_export_lists_tools_in_name_order() -> None:
    names = [t["function"]["name"] for t in export_schemas(make_sample_registry(), "openai")]
    assert names == ["echo", "ping"]


def test_anthropic_uses_input_schema_key() -> None:
    tool = export_schemas(make_sample_registry(), "anthropic")[0]
    assert set(tool) == {"name", "description", "input_schema"}


def test_mcp_has_input_and_output_schema() -> None:
    tool = export_schemas(make_sample_registry(), "mcp")[0]
    assert set(tool) == {"name", "description", "inputSchema", "outputSchema"}
    assert "lines" in tool["outputSchema"]["properties"]


class Titled(ToolInput):
    title: str = Field(default="x", description="A field that is literally named title.")
    tags: list[str] = Field(default_factory=lambda: ["a"])


class TitledOut(ToolOutput):
    title: str


def test_titles_are_stripped_but_fields_named_title_survive() -> None:
    registry = Registry()

    @registry.tool
    def titled(args: Titled, ctx: Context) -> TitledOut:
        """Has a field called title."""
        return TitledOut(title=args.title)

    schema = export_schemas(registry, "anthropic")[0]["input_schema"]
    assert "title" not in schema
    assert "title" in schema["properties"]
    assert "title" not in schema["properties"]["tags"]
    assert schema["properties"]["title"]["default"] == "x"
