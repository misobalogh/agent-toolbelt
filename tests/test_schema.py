from collections.abc import Callable
from typing import Any

from sample_tools import make_sample_registry

from toolbelt.adapters.schema import export_schemas


def test_openai_export_matches_snapshot(assert_snapshot: Callable[[str, Any], None]) -> None:
    assert_snapshot("sample_openai", export_schemas(make_sample_registry(), "openai"))


def test_openai_export_lists_tools_in_name_order() -> None:
    names = [t["function"]["name"] for t in export_schemas(make_sample_registry(), "openai")]
    assert names == ["echo", "ping"]
