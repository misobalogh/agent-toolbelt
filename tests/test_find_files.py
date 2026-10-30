from pathlib import Path

import pytest

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import ErrorCode, InvalidInput, LimitExceeded, NotFound, ToolError
from toolbelt.core.limits import Limits
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.find_files import FindFilesOutput


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    (root / "docs" / "deep").mkdir(parents=True)
    (root / "top.txt").write_text("t")
    (root / "docs" / "a.md").write_text("aa")
    (root / "docs" / "b.txt").write_text("bbb")
    (root / "docs" / "deep" / "c.md").write_text("cccc")
    return Sandbox(root)


def run(box: Sandbox, args: dict[str, object], limits: Limits | None = None) -> FindFilesOutput:
    result = default_registry.call("find_files", args, box, limits)
    assert isinstance(result, FindFilesOutput)
    return result


def paths(out: FindFilesOutput) -> list[str]:
    return [m.path for m in out.matches]


def test_matches_in_the_top_directory(box: Sandbox) -> None:
    assert paths(run(box, {"pattern": "*.txt"})) == ["top.txt"]


def test_recursive_pattern(box: Sandbox) -> None:
    assert paths(run(box, {"pattern": "**/*.md"})) == ["docs/a.md", "docs/deep/c.md"]


def test_search_from_a_subdirectory(box: Sandbox) -> None:
    out = run(box, {"pattern": "**/*", "path": "docs"})
    assert paths(out) == ["docs/a.md", "docs/b.txt", "docs/deep/c.md"]


def test_directories_are_not_returned(box: Sandbox) -> None:
    assert paths(run(box, {"pattern": "d*"})) == []


def test_sizes_are_reported(box: Sandbox) -> None:
    assert run(box, {"pattern": "**/c.md"}).matches[0].size == 4


def test_results_are_truncated_at_the_limit(box: Sandbox) -> None:
    out = run(box, {"pattern": "**/*"}, Limits(max_entries=2))
    assert len(out.matches) == 2
    assert out.truncated


def test_request_above_the_limit_is_rejected(box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        run(box, {"pattern": "*", "max_results": 10**6})


@pytest.mark.parametrize("pattern", ["", "/etc/*", "../*", "docs/../../*"])
def test_bad_patterns_are_invalid_input(box: Sandbox, pattern: str) -> None:
    with pytest.raises(InvalidInput):
        run(box, {"pattern": pattern})


def test_missing_base_directory_is_not_found(box: Sandbox) -> None:
    with pytest.raises(NotFound):
        run(box, {"pattern": "*", "path": "nope"})


@pytest.mark.parametrize("path", ["..", "/etc", "docs/../.."])
def test_escaping_base_directories_are_rejected(box: Sandbox, path: str) -> None:
    with pytest.raises(ToolError) as info:
        run(box, {"pattern": "*", "path": path})
    assert info.value.code is ErrorCode.OUTSIDE_SANDBOX
