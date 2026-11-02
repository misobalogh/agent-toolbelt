from pathlib import Path

import pytest

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import (
    AlreadyExists,
    ErrorCode,
    LimitExceeded,
    SandboxViolation,
    ToolError,
)
from toolbelt.core.limits import Limits
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.write_text import WriteTextOutput


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    root.mkdir()
    return Sandbox(root, allow_write=True)


def run(box: Sandbox, args: dict[str, object], limits: Limits | None = None) -> WriteTextOutput:
    result = default_registry.call("write_text", args, box, limits)
    assert isinstance(result, WriteTextOutput)
    return result


def test_writes_utf8_text(box: Sandbox) -> None:
    out = run(box, {"path": "a.txt", "text": "caf\u00e9"})
    assert (out.path, out.bytes_written) == ("a.txt", 5)
    assert (box.root / "a.txt").read_bytes() == "caf\u00e9".encode()


def test_read_only_sandbox_refuses_to_write(tmp_path: Path) -> None:
    read_only = Sandbox(tmp_path)
    with pytest.raises(ToolError) as info:
        run(read_only, {"path": "a.txt", "text": "x"})
    assert info.value.code is ErrorCode.WRITE_DISABLED
    assert not (tmp_path / "a.txt").exists()


def test_existing_file_is_kept_without_overwrite(box: Sandbox) -> None:
    run(box, {"path": "a.txt", "text": "one"})
    with pytest.raises(AlreadyExists):
        run(box, {"path": "a.txt", "text": "two"})
    assert (box.root / "a.txt").read_text() == "one"


def test_overwrite_and_create_parents(box: Sandbox) -> None:
    run(box, {"path": "d/a.txt", "text": "one", "create_parents": True})
    run(box, {"path": "d/a.txt", "text": "two", "overwrite": True})
    assert (box.root / "d" / "a.txt").read_text() == "two"


def test_oversized_text_is_rejected_before_writing(box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        run(box, {"path": "big.txt", "text": "x" * 101}, Limits(max_write_bytes=100))
    assert not (box.root / "big.txt").exists()


def test_text_exactly_at_the_limit_is_written(box: Sandbox) -> None:
    run(box, {"path": "ok.txt", "text": "x" * 100}, Limits(max_write_bytes=100))
    assert (box.root / "ok.txt").stat().st_size == 100


@pytest.mark.parametrize("path", ["../x.txt", "/tmp/x.txt", "a/../../x.txt"])
def test_escape_attempts_are_rejected(box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        run(box, {"path": path, "text": "x", "create_parents": True})
