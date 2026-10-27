from pathlib import Path

import pytest

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import NotFound, SandboxViolation
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.file_info import FileInfoOutput


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "notes.txt").write_text("hello")
    (root / "blob").write_bytes(b"\x00\x01")
    return Sandbox(root)


def run(box: Sandbox, path: str) -> FileInfoOutput:
    result = default_registry.call("file_info", {"path": path}, box)
    assert isinstance(result, FileInfoOutput)
    return result


def test_file_info_for_a_text_file(box: Sandbox) -> None:
    out = run(box, "notes.txt")
    assert (out.path, out.kind, out.size) == ("notes.txt", "file", 5)
    assert out.mime_type == "text/plain"
    assert out.modified.tzinfo is not None


def test_file_info_for_a_directory(box: Sandbox) -> None:
    out = run(box, "sub")
    assert (out.kind, out.mime_type) == ("dir", None)


def test_unknown_extension_has_no_mime_type(box: Sandbox) -> None:
    assert run(box, "blob").mime_type is None


def test_missing_path_is_not_found(box: Sandbox) -> None:
    with pytest.raises(NotFound):
        run(box, "missing.txt")


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "sub/../../x"])
def test_escape_attempts_are_rejected(box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        run(box, path)
