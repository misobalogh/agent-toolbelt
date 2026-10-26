from collections.abc import Callable
from typing import Any

import pytest

import toolbelt.tools  # noqa: F401  (registers the tools)
from toolbelt.adapters.schema import FORMATS, SchemaFormat, export_schemas
from toolbelt.core.registry import default_registry


@pytest.mark.parametrize("fmt", FORMATS)
def test_real_tool_schemas_match_snapshot(
    fmt: SchemaFormat, assert_snapshot: Callable[[str, Any], None]
) -> None:
    assert_snapshot(f"tools_{fmt}", export_schemas(default_registry, fmt))
