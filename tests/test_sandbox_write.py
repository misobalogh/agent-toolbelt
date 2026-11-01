from pathlib import Path

import pytest

from toolbelt.core.errors import (
    AlreadyExists,
    ErrorCode,
    InvalidInput,
    NotFound,
    SandboxViolation,
    ToolError,
)
from toolbelt.core.sandbox import Sandbox


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    root.mkdir()
    return Sandbox(root, allow_write=True)


def write(box: Sandbox, raw: str, data: bytes = b"x", **kwargs: bool) -> None:
    with box.open_write(raw, **kwargs) as handle:
        handle.write(data)


def test_writing_is_off_by_default(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as info:
        Sandbox(tmp_path).open_write("a.txt")
    assert info.value.code is ErrorCode.WRITE_DISABLED
    assert not (tmp_path / "a.txt").exists()


def test_creates_a_new_file(box: Sandbox) -> None:
    write(box, "a.txt", b"hello")
    assert (box.root / "a.txt").read_bytes() == b"hello"


def test_refuses_to_overwrite_by_default(box: Sandbox) -> None:
    write(box, "a.txt", b"one")
    with pytest.raises(AlreadyExists):
        write(box, "a.txt", b"two")
    assert (box.root / "a.txt").read_bytes() == b"one"


def test_overwrite_replaces_the_content(box: Sandbox) -> None:
    write(box, "a.txt", b"one")
    write(box, "a.txt", b"two", overwrite=True)
    assert (box.root / "a.txt").read_bytes() == b"two"


def test_missing_parent_needs_create_parents(box: Sandbox) -> None:
    with pytest.raises(NotFound):
        write(box, "new/dir/a.txt")
    write(box, "new/dir/a.txt", create_parents=True)
    assert (box.root / "new" / "dir" / "a.txt").exists()


def test_writing_to_a_directory_is_rejected(box: Sandbox) -> None:
    (box.root / "d").mkdir()
    with pytest.raises(ToolError):
        write(box, "d", overwrite=True)


def test_writing_to_the_root_is_rejected(box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        write(box, ".", overwrite=True)


@pytest.mark.parametrize("raw", ["../x.txt", "/tmp/x.txt", "d/../../x.txt"])
def test_escape_attempts_are_rejected_and_create_nothing(box: Sandbox, raw: str) -> None:
    with pytest.raises(SandboxViolation):
        write(box, raw, create_parents=True)
    assert not (box.root.parent / "x.txt").exists()


def test_symlink_pointing_outside_cannot_be_written_through(box: Sandbox, tmp_path: Path) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("original")
    (box.root / "link.txt").symlink_to(target)
    with pytest.raises(SandboxViolation):
        write(box, "link.txt", b"pwned", overwrite=True)
    assert target.read_text() == "original"


def test_create_parents_does_not_create_dirs_outside(box: Sandbox, tmp_path: Path) -> None:
    (box.root / "link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SandboxViolation):
        write(box, "link/newdir/a.txt", create_parents=True)
    assert not (tmp_path / "newdir").exists()
