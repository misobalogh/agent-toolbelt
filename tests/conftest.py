import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


@pytest.fixture
def assert_snapshot() -> Callable[[str, Any], None]:
    """Compare data with tests/snapshots/<name>.json.

    Regenerate with `UPDATE_SNAPSHOTS=1 uv run pytest` and review the diff.
    """

    def check(name: str, data: Any) -> None:
        path = SNAPSHOT_DIR / f"{name}.json"
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        if os.environ.get("UPDATE_SNAPSHOTS"):
            path.write_text(text)
        assert path.exists(), f"missing snapshot {path.name}, run with UPDATE_SNAPSHOTS=1"
        assert path.read_text() == text, f"snapshot {path.name} is out of date"

    return check
