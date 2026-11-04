"""Extract a zip or tar archive into the sandbox, with zip bomb and traversal protection."""

from __future__ import annotations

import stat
import tarfile
import zipfile
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial
from pathlib import PurePosixPath
from typing import IO, BinaryIO, cast

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.errors import ErrorCode, LimitExceeded, SandboxViolation, ToolError, Unsupported
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import tool

CHUNK_BYTES = 64 * 1024
# Below this size a high compression ratio is normal (a text file full of spaces).
RATIO_CHECK_MIN_BYTES = 1_048_576


class ExtractArchiveInput(ToolInput):
    archive: str = Field(description="Zip or tar archive, relative to the sandbox root.")
    dest: str = Field(default=".", description="Directory to extract into. Created if missing.")


class ExtractArchiveOutput(ToolOutput):
    files: list[str] = Field(description="Root-relative paths of the extracted files.")
    total_bytes: int


@dataclass(frozen=True)
class _Member:
    name: str
    size: int
    is_dir: bool
    is_plain: bool
    open: Callable[[], IO[bytes]]


@tool
def extract_archive(args: ExtractArchiveInput, ctx: Context) -> ExtractArchiveOutput:
    """Extract the files of a zip or tar archive. Empty directories are not recreated."""
    ctx.sandbox.ensure_writable()
    archive_size = ctx.sandbox.stat(args.archive).st_size
    with ctx.sandbox.open_read(args.archive) as handle:
        try:
            with _open_archive(handle) as archive:
                members = _list_members(archive, ctx)
                _check_limits(members, archive_size, ctx)
                return _extract(members, args.dest, ctx)
        except (zipfile.BadZipFile, tarfile.TarError, zlib.error, EOFError) as exc:
            raise ToolError(
                f"archive is corrupt: {exc}",
                hint="the file may be truncated or damaged, try to obtain it again",
                code=ErrorCode.CORRUPT,
            ) from exc


def _open_archive(handle: BinaryIO) -> zipfile.ZipFile | tarfile.TarFile:
    if zipfile.is_zipfile(handle):
        return zipfile.ZipFile(handle)
    handle.seek(0)  # is_zipfile moved the position
    try:
        return tarfile.open(fileobj=handle, mode="r:*")
    except tarfile.TarError:
        raise Unsupported(
            "not a zip or tar archive",
            hint="supported formats: .zip, .tar, .tar.gz, .tar.bz2, .tar.xz",
        ) from None


def _list_members(archive: zipfile.ZipFile | tarfile.TarFile, ctx: Context) -> list[_Member]:
    members: list[_Member] = []
    for member in _iter_members(archive):
        ctx.deadline.check()
        if not member.is_plain:
            raise Unsupported(
                f"archive entry is a link or special file: {member.name!r}",
                hint="only regular files and directories are extracted, the archive is unsafe",
            )
        members.append(member)
        if len(members) > ctx.limits.max_extract_files:
            raise LimitExceeded(
                f"archive has more than {ctx.limits.max_extract_files} entries",
                hint="extract a smaller archive",
            )
    return members


def _iter_members(archive: zipfile.ZipFile | tarfile.TarFile) -> Iterator[_Member]:
    if isinstance(archive, zipfile.ZipFile):
        for zinfo in archive.infolist():
            mode = zinfo.external_attr >> 16
            plain = not stat.S_ISLNK(mode) and stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)
            yield _Member(
                zinfo.filename, zinfo.file_size, zinfo.is_dir(), plain, partial(archive.open, zinfo)
            )
    else:
        for tinfo in archive:
            plain = tinfo.isfile() or tinfo.isdir()
            yield _Member(
                tinfo.name, tinfo.size, tinfo.isdir(), plain, partial(_open_tar, archive, tinfo)
            )


def _open_tar(archive: tarfile.TarFile, info: tarfile.TarInfo) -> IO[bytes]:
    return cast(IO[bytes], archive.extractfile(info))


def _check_limits(members: list[_Member], archive_size: int, ctx: Context) -> None:
    total = sum(m.size for m in members)
    if total > ctx.limits.max_extract_bytes:
        raise LimitExceeded(
            f"archive would expand to {total} bytes, the limit is {ctx.limits.max_extract_bytes}",
            hint="extract a smaller archive",
        )
    if total > RATIO_CHECK_MIN_BYTES and total > archive_size * ctx.limits.max_compression_ratio:
        raise LimitExceeded(
            f"compression ratio above {ctx.limits.max_compression_ratio}:1, possible zip bomb",
            hint="do not extract archives from sources you do not trust",
        )


def _extract(
    members: list[_Member],
    dest: str,
    ctx: Context,
) -> ExtractArchiveOutput:
    extracted: list[str] = []
    total = 0
    for member in members:
        if member.is_dir:
            continue
        target = _member_path(dest, member.name)
        with member.open() as source, ctx.sandbox.open_write(target, create_parents=True) as out:
            while chunk := source.read(CHUNK_BYTES):
                ctx.deadline.check()
                out.write(chunk)
                total += len(chunk)
        extracted.append(ctx.sandbox.display(ctx.sandbox.resolve(target)))
    return ExtractArchiveOutput(files=extracted, total_bytes=total)


def _member_path(dest: str, name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\x00" in name:
        raise SandboxViolation(
            f"archive entry would escape the destination: {name!r}",
            hint="the archive is unsafe, do not extract it",
        )
    return f"{dest}/{path}"
