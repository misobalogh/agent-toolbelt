from pathlib import Path

import pytest

from toolbelt.core.errors import ErrorCode, NotFound, SandboxViolation, ToolError
from toolbelt.core.sandbox import Sandbox


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "b.txt").write_text("bbb")
    (root / "a.txt").write_text("a")
    (root / "sub" / "c.txt").write_text("cc")
    return Sandbox(root)


def test_stat_returns_size(box: Sandbox) -> None:
    assert box.stat("b.txt").st_size == 3


def test_stat_missing_raises_not_found(box: Sandbox) -> None:
    with pytest.raises(NotFound):
        box.stat("nope.txt")


def test_open_read_reads_bytes(box: Sandbox) -> None:
    with box.open_read("sub/c.txt") as handle:
        assert handle.read() == b"cc"


def test_open_read_rejects_directories(box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        box.open_read("sub")
    assert info.value.code is ErrorCode.NOT_A_FILE


def test_open_read_missing_raises_not_found(box: Sandbox) -> None:
    with pytest.raises(NotFound):
        box.open_read("nope.txt")


def test_list_dir_is_sorted_and_typed(box: Sandbox) -> None:
    entries = box.list_dir(".")
    assert [(e.name, e.kind) for e in entries] == [
        ("a.txt", "file"),
        ("b.txt", "file"),
        ("sub", "dir"),
    ]
    assert [e.path for e in box.list_dir("sub")] == ["sub/c.txt"]


def test_list_dir_rejects_files(box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        box.list_dir("a.txt")
    assert info.value.code is ErrorCode.NOT_A_DIRECTORY


def test_list_dir_reports_symlinks_without_following(box: Sandbox, tmp_path: Path) -> None:
    (box.root / "link").symlink_to(tmp_path)
    kinds = {e.name: e.kind for e in box.list_dir(".")}
    assert kinds["link"] == "symlink"


def test_stat_through_escaping_symlink_is_rejected(box: Sandbox, tmp_path: Path) -> None:
    (box.root / "link").symlink_to(tmp_path)
    with pytest.raises(SandboxViolation):
        box.stat("link")
