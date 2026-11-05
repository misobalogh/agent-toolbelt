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


def test_input_path_returns_the_resolved_file(box: Sandbox) -> None:
    (box.root / "a.bin").write_bytes(b"x")
    assert box.input_path("a.bin") == box.root / "a.bin"


def test_input_path_rejects_missing_and_directories(box: Sandbox) -> None:
    (box.root / "d").mkdir()
    with pytest.raises(NotFound):
        box.input_path("nope.bin")
    with pytest.raises(ToolError) as info:
        box.input_path("d")
    assert info.value.code is ErrorCode.NOT_A_FILE


@pytest.mark.parametrize("raw", ["../x", "/etc/passwd", "a/../../x"])
def test_input_path_rejects_escapes(box: Sandbox, raw: str) -> None:
    with pytest.raises(SandboxViolation):
        box.input_path(raw)


def test_input_path_rejects_a_symlink_leaving_the_root(box: Sandbox, tmp_path: Path) -> None:
    (tmp_path / "secret.bin").write_bytes(b"s")
    (box.root / "link.bin").symlink_to(tmp_path / "secret.bin")
    with pytest.raises(SandboxViolation):
        box.input_path("link.bin")


def test_output_path_is_not_created(box: Sandbox) -> None:
    path = box.output_path("out.bin")
    assert path == box.root / "out.bin"
    assert not path.exists()


def test_output_path_needs_a_writable_sandbox(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as info:
        Sandbox(tmp_path).output_path("out.bin")
    assert info.value.code is ErrorCode.WRITE_DISABLED


def test_output_path_refuses_existing_file_without_overwrite(box: Sandbox) -> None:
    (box.root / "out.bin").write_bytes(b"x")
    with pytest.raises(AlreadyExists):
        box.output_path("out.bin")
    assert box.output_path("out.bin", overwrite=True) == box.root / "out.bin"


def test_output_path_missing_parent_needs_create_parents(box: Sandbox) -> None:
    with pytest.raises(NotFound):
        box.output_path("new/out.bin")
    assert not (box.root / "new").exists()
    box.output_path("new/out.bin", create_parents=True)
    assert (box.root / "new").is_dir()


def test_output_path_rejects_directory_and_root(box: Sandbox) -> None:
    (box.root / "d").mkdir()
    with pytest.raises(ToolError) as info:
        box.output_path("d", overwrite=True)
    assert info.value.code is ErrorCode.NOT_A_FILE
    with pytest.raises(InvalidInput):
        box.output_path(".")


@pytest.mark.parametrize("raw", ["../x", "/tmp/x", "a/../../x"])
def test_output_path_rejects_escapes_without_creating_parents(box: Sandbox, raw: str) -> None:
    with pytest.raises(SandboxViolation):
        box.output_path(raw, create_parents=True)
    assert not (box.root / "a").exists()


def test_output_path_rejects_a_symlink_leaving_the_root(box: Sandbox, tmp_path: Path) -> None:
    (box.root / "link.bin").symlink_to(tmp_path / "outside.bin")
    with pytest.raises(SandboxViolation):
        box.output_path("link.bin", overwrite=True)
