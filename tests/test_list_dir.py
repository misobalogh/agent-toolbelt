from pathlib import Path

import pytest

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import ErrorCode, LimitExceeded, SandboxViolation, ToolError
from toolbelt.core.limits import Limits
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.list_dir import ListDirOutput


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("a")
    (root / ".hidden").write_text("h")
    (root / "sub" / "b.txt").write_text("bb")
    return Sandbox(root)


def run(box: Sandbox, args: dict[str, object], limits: Limits | None = None) -> ListDirOutput:
    result = default_registry.call("list_dir", args, box, limits)
    assert isinstance(result, ListDirOutput)
    return result


def test_lists_root_without_hidden_files(box: Sandbox) -> None:
    out = run(box, {})
    assert out.path == "."
    assert [(e.name, e.kind) for e in out.entries] == [("a.txt", "file"), ("sub", "dir")]
    assert not out.truncated


def test_include_hidden(box: Sandbox) -> None:
    names = [e.name for e in run(box, {"include_hidden": True}).entries]
    assert ".hidden" in names


def test_lists_subdirectory_with_root_relative_paths(box: Sandbox) -> None:
    out = run(box, {"path": "sub"})
    assert [e.path for e in out.entries] == ["sub/b.txt"]


def test_file_instead_of_directory_is_a_typed_error(box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        run(box, {"path": "a.txt"})
    assert info.value.code is ErrorCode.NOT_A_DIRECTORY


def test_oversized_directory_is_truncated(box: Sandbox) -> None:
    for i in range(10):
        (box.root / f"f{i}.txt").write_text("x")
    out = run(box, {}, Limits(max_entries=4))
    assert len(out.entries) == 4
    assert out.truncated


def test_requesting_more_than_the_limit_is_rejected(box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        run(box, {"max_entries": 5000})


@pytest.mark.parametrize("path", ["..", "/etc", "sub/../.."])
def test_escape_attempts_are_rejected(box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        run(box, {"path": path})
