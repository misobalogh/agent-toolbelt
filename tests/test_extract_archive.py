import io
import tarfile
import zipfile
from pathlib import Path

import pytest

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import ErrorCode, LimitExceeded, SandboxViolation, ToolError
from toolbelt.core.limits import Limits
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.extract_archive import ExtractArchiveOutput


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    root = tmp_path / "root"
    root.mkdir()
    return Sandbox(root, allow_write=True)


def run(
    box: Sandbox, args: dict[str, object], limits: Limits | None = None
) -> ExtractArchiveOutput:
    result = default_registry.call("extract_archive", args, box, limits)
    assert isinstance(result, ExtractArchiveOutput)
    return result


def make_zip(path: Path, files: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> None:
    with zipfile.ZipFile(path, "w", compression) as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def make_tar(path: Path, files: dict[str, bytes], mode: str = "w") -> None:
    with tarfile.open(path, mode) as tf:  # type: ignore[call-overload]
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_extracts_a_zip(box: Sandbox) -> None:
    make_zip(box.root / "a.zip", {"x.txt": b"xx", "sub/y.txt": b"yyy"})
    out = run(box, {"archive": "a.zip", "dest": "out"})
    assert out.files == ["out/x.txt", "out/sub/y.txt"]
    assert out.total_bytes == 5
    assert (box.root / "out" / "sub" / "y.txt").read_bytes() == b"yyy"


@pytest.mark.parametrize(
    ("name", "mode"), [("a.tar", "w"), ("a.tar.gz", "w:gz"), ("a.tar.xz", "w:xz")]
)
def test_extracts_tar_variants(box: Sandbox, name: str, mode: str) -> None:
    make_tar(box.root / name, {"d/x.txt": b"hello"}, mode)
    out = run(box, {"archive": name})
    assert out.files == ["d/x.txt"]
    assert (box.root / "d" / "x.txt").read_bytes() == b"hello"


def test_read_only_sandbox_refuses_to_extract(tmp_path: Path) -> None:
    make_zip(tmp_path / "a.zip", {"x.txt": b"x"})
    with pytest.raises(ToolError) as info:
        run(Sandbox(tmp_path), {"archive": "a.zip"})
    assert info.value.code is ErrorCode.WRITE_DISABLED


def test_garbage_is_not_an_archive(box: Sandbox) -> None:
    (box.root / "a.zip").write_bytes(b"this is not an archive at all" * 50)
    with pytest.raises(ToolError) as info:
        run(box, {"archive": "a.zip"})
    assert info.value.code is ErrorCode.UNSUPPORTED


def test_damaged_zip_member_is_reported_as_corrupt(box: Sandbox) -> None:
    make_zip(box.root / "a.zip", {"x.txt": b"A" * 100}, zipfile.ZIP_STORED)
    raw = bytearray((box.root / "a.zip").read_bytes())
    raw[raw.index(b"AAAA")] = ord("B")
    (box.root / "a.zip").write_bytes(raw)
    with pytest.raises(ToolError) as info:
        run(box, {"archive": "a.zip"})
    assert info.value.code is ErrorCode.CORRUPT


@pytest.mark.parametrize("name", ["../evil.txt", "/tmp/evil.txt", "a/../../evil.txt"])
def test_zip_slip_is_rejected(box: Sandbox, name: str) -> None:
    make_zip(box.root / "evil.zip", {name: b"pwned"})
    with pytest.raises(SandboxViolation):
        run(box, {"archive": "evil.zip", "dest": "out"})
    assert not (box.root / "evil.txt").exists()
    assert not (box.root.parent / "evil.txt").exists()


def test_tar_traversal_is_rejected(box: Sandbox) -> None:
    make_tar(box.root / "evil.tar", {"../evil.txt": b"pwned"})
    with pytest.raises(SandboxViolation):
        run(box, {"archive": "evil.tar", "dest": "out"})
    assert not (box.root / "evil.txt").exists()


def test_too_many_entries_are_rejected(box: Sandbox) -> None:
    make_zip(box.root / "many.zip", {f"f{i}.txt": b"x" for i in range(20)})
    with pytest.raises(LimitExceeded):
        run(box, {"archive": "many.zip", "dest": "out"}, Limits(max_extract_files=10))
    assert not (box.root / "out").exists()


def test_oversized_expansion_is_rejected_before_writing(box: Sandbox) -> None:
    make_zip(box.root / "big.zip", {"big.bin": b"x" * 5000})
    with pytest.raises(LimitExceeded):
        run(box, {"archive": "big.zip", "dest": "out"}, Limits(max_extract_bytes=1000))
    assert not (box.root / "out").exists()


def test_zip_bomb_is_rejected_by_compression_ratio(box: Sandbox) -> None:
    make_zip(box.root / "bomb.zip", {"zeros.bin": bytes(5_000_000)})
    assert (box.root / "bomb.zip").stat().st_size < 50_000
    with pytest.raises(LimitExceeded) as info:
        run(box, {"archive": "bomb.zip", "dest": "out"})
    assert "zip bomb" in info.value.message
    assert not (box.root / "out").exists()


def test_existing_files_are_not_overwritten(box: Sandbox) -> None:
    (box.root / "out").mkdir()
    (box.root / "out" / "x.txt").write_text("keep")
    make_zip(box.root / "a.zip", {"x.txt": b"new"})
    with pytest.raises(ToolError) as info:
        run(box, {"archive": "a.zip", "dest": "out"})
    assert info.value.code is ErrorCode.ALREADY_EXISTS
    assert (box.root / "out" / "x.txt").read_text() == "keep"


@pytest.mark.parametrize("dest", ["../out", "/tmp/out"])
def test_destination_outside_the_root_is_rejected(box: Sandbox, dest: str) -> None:
    make_zip(box.root / "a.zip", {"x.txt": b"x"})
    with pytest.raises(SandboxViolation):
        run(box, {"archive": "a.zip", "dest": dest})


def test_archive_outside_the_root_is_rejected(box: Sandbox, tmp_path: Path) -> None:
    make_zip(tmp_path / "outside.zip", {"x.txt": b"x"})
    with pytest.raises(SandboxViolation):
        run(box, {"archive": str(tmp_path / "outside.zip")})
