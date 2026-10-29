from pathlib import Path

import pytest

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import ErrorCode, InvalidInput, LimitExceeded, NotFound, ToolError
from toolbelt.core.limits import Limits
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.read_text import ReadTextOutput


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    root.mkdir()
    return Sandbox(root)


def run(box: Sandbox, args: dict[str, object], limits: Limits | None = None) -> ReadTextOutput:
    result = default_registry.call("read_text", args, box, limits)
    assert isinstance(result, ReadTextOutput)
    return result


def test_reads_plain_utf8(box: Sandbox) -> None:
    (box.root / "a.txt").write_text("hello", encoding="utf-8")
    out = run(box, {"path": "a.txt"})
    assert (out.text, out.encoding, out.truncated) == ("hello", "utf-8", False)
    assert (out.bytes_read, out.total_bytes) == (5, 5)


def test_detects_utf8_bom_and_strips_it(box: Sandbox) -> None:
    (box.root / "a.txt").write_bytes(b"\xef\xbb\xbfhello")
    out = run(box, {"path": "a.txt"})
    assert (out.text, out.encoding) == ("hello", "utf-8-sig")


def test_detects_utf16_with_bom(box: Sandbox) -> None:
    (box.root / "a.txt").write_bytes("hi there".encode("utf-16"))
    out = run(box, {"path": "a.txt"})
    assert (out.text, out.encoding) == ("hi there", "utf-16")


def test_falls_back_to_cp1252_for_legacy_files(box: Sandbox) -> None:
    (box.root / "a.txt").write_bytes(b"caf\xe9")
    out = run(box, {"path": "a.txt"})
    assert (out.text, out.encoding) == ("caf\u00e9", "cp1252")


def test_explicit_encoding_wins(box: Sandbox) -> None:
    (box.root / "a.txt").write_bytes("\u010de\u0161".encode("cp1250"))
    assert run(box, {"path": "a.txt", "encoding": "cp1250"}).text == "\u010de\u0161"


def test_unknown_encoding_is_invalid_input(box: Sandbox) -> None:
    (box.root / "a.txt").write_text("x")
    with pytest.raises(InvalidInput):
        run(box, {"path": "a.txt", "encoding": "not-a-codec"})


def test_binary_file_is_unsupported(box: Sandbox) -> None:
    (box.root / "a.bin").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
    with pytest.raises(ToolError) as info:
        run(box, {"path": "a.bin"})
    assert info.value.code is ErrorCode.UNSUPPORTED


def test_large_file_is_truncated_with_info(box: Sandbox) -> None:
    (box.root / "big.txt").write_text("x" * 1000)
    out = run(box, {"path": "big.txt", "max_bytes": 100})
    assert (out.bytes_read, out.total_bytes, out.truncated) == (100, 1000, True)
    assert out.text == "x" * 100


def test_file_exactly_at_the_limit_is_not_truncated(box: Sandbox) -> None:
    (box.root / "a.txt").write_text("x" * 100)
    assert not run(box, {"path": "a.txt", "max_bytes": 100}).truncated


def test_default_limit_comes_from_limits(box: Sandbox) -> None:
    (box.root / "big.txt").write_text("x" * 1000)
    out = run(box, {"path": "big.txt"}, Limits(max_read_bytes=50))
    assert (out.bytes_read, out.truncated) == (50, True)


def test_request_above_the_limit_is_rejected(box: Sandbox) -> None:
    (box.root / "a.txt").write_text("x")
    with pytest.raises(LimitExceeded):
        run(box, {"path": "a.txt", "max_bytes": 10**9})


def test_missing_file_is_not_found(box: Sandbox) -> None:
    with pytest.raises(NotFound):
        run(box, {"path": "nope.txt"})


def test_directory_is_not_a_file(box: Sandbox) -> None:
    (box.root / "d").mkdir()
    with pytest.raises(ToolError) as info:
        run(box, {"path": "d"})
    assert info.value.code is ErrorCode.NOT_A_FILE


@pytest.mark.parametrize("path", ["../x.txt", "/etc/passwd", "d/../../x"])
def test_escape_attempts_are_rejected(box: Sandbox, path: str) -> None:
    with pytest.raises(ToolError) as info:
        run(box, {"path": path})
    assert info.value.code is ErrorCode.OUTSIDE_SANDBOX


def test_truncation_inside_a_multibyte_character_keeps_utf8(box: Sandbox) -> None:
    (box.root / "a.txt").write_text("\u00e9" * 100, encoding="utf-8")
    out = run(box, {"path": "a.txt", "max_bytes": 101})
    assert out.encoding == "utf-8"
    assert out.text == "\u00e9" * 50
    assert out.truncated
