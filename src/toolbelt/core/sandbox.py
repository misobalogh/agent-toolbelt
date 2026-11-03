"""All filesystem access goes through a Sandbox bound to one root directory."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from toolbelt.core.errors import (
    AlreadyExists,
    ErrorCode,
    InvalidInput,
    NotFound,
    PermissionDenied,
    SandboxViolation,
    ToolError,
)

EntryKind = Literal["file", "dir", "symlink", "other"]


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    kind: EntryKind
    size: int


def kind_of(mode: int) -> EntryKind:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "other"


class Sandbox:
    def __init__(self, root: str | Path, *, allow_write: bool = False) -> None:
        resolved = Path(root).resolve()
        if not resolved.is_dir():
            raise InvalidInput(f"sandbox root is not a directory: {root}")
        self._root = resolved
        self._allow_write = allow_write

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, raw: str) -> Path:
        """Map a user-supplied path to a real path inside the root.

        Relative paths are taken relative to the root. Symlinks are followed
        before the containment check, so a link cannot lead outside.
        """
        if "\x00" in raw:
            raise InvalidInput("path contains a NUL byte", hint="remove the NUL character")
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self._root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self._root):
            raise SandboxViolation(
                f"path is outside the sandbox: {raw}",
                hint="use a path relative to the sandbox root",
            )
        return resolved

    def display(self, resolved: Path) -> str:
        """Root-relative POSIX form of an already resolved path."""
        return resolved.relative_to(self._root).as_posix()

    def stat(self, raw: str) -> os.stat_result:
        resolved = self.resolve(raw)
        try:
            return resolved.stat()
        except FileNotFoundError:
            raise _missing(raw) from None
        except PermissionError:
            raise _denied(raw) from None

    def open_read(self, raw: str) -> BinaryIO:
        resolved = self.resolve(raw)
        try:
            if not resolved.is_file():
                if not resolved.exists():
                    raise _missing(raw)
                raise ToolError(
                    f"not a regular file: {raw}",
                    hint="use list_dir to see what the directory contains",
                    code=ErrorCode.NOT_A_FILE,
                )
            return resolved.open("rb")
        except PermissionError:
            raise _denied(raw) from None

    def ensure_writable(self) -> None:
        if not self._allow_write:
            raise ToolError(
                "writing is disabled in this sandbox",
                hint="the operator must create the Sandbox with allow_write=True",
                code=ErrorCode.WRITE_DISABLED,
            )

    def open_write(
        self, raw: str, *, overwrite: bool = False, create_parents: bool = False
    ) -> BinaryIO:
        self.ensure_writable()
        resolved = self.resolve(raw)
        if resolved == self._root:
            raise InvalidInput("cannot write to the sandbox root itself")
        if not resolved.parent.is_dir():
            if not create_parents:
                raise NotFound(
                    f"parent directory does not exist: {self.display(resolved.parent)}",
                    hint="set create_parents to true or create the directory first",
                )
            resolved.parent.mkdir(parents=True, exist_ok=True)
        try:
            return resolved.open("wb" if overwrite else "xb")
        except FileExistsError:
            raise AlreadyExists(
                f"file already exists: {raw}", hint="set overwrite to true to replace it"
            ) from None
        except IsADirectoryError:
            raise ToolError(f"not a regular file: {raw}", code=ErrorCode.NOT_A_FILE) from None
        except (PermissionError, NotADirectoryError):
            raise _denied(raw) from None

    def list_dir(self, raw: str) -> list[Entry]:
        resolved = self.resolve(raw)
        if not resolved.exists():
            raise _missing(raw)
        if not resolved.is_dir():
            raise ToolError(
                f"not a directory: {raw}",
                hint="use file_info or read_text for files",
                code=ErrorCode.NOT_A_DIRECTORY,
            )
        try:
            children = sorted(resolved.iterdir(), key=lambda p: p.name)
        except PermissionError:
            raise _denied(raw) from None
        entries = []
        for child in children:
            info = child.lstat()
            entries.append(
                Entry(child.name, self.display(child), kind_of(info.st_mode), info.st_size)
            )
        return entries

    def glob(self, raw_base: str, pattern: str) -> Iterator[Entry]:
        """Yield regular files below `raw_base` that match a glob pattern."""
        if not pattern or Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise InvalidInput(
                f"invalid glob pattern: {pattern!r}",
                hint="use a relative pattern without '..', for example '**/*.txt'",
            )
        base = self.resolve(raw_base)
        if not base.is_dir():
            raise _missing(raw_base)
        for match in base.glob(pattern):
            try:
                target = match.resolve(strict=True)
                info = target.stat()
            except OSError:
                continue
            # A link below the base may still lead out of the root.
            if target.is_relative_to(self._root) and stat.S_ISREG(info.st_mode):
                yield Entry(match.name, self.display(match), "file", info.st_size)


def _missing(raw: str) -> NotFound:
    return NotFound(f"no such file or directory: {raw}", hint="use list_dir to find valid paths")


def _denied(raw: str) -> PermissionDenied:
    return PermissionDenied(f"permission denied: {raw}", hint="choose a different path")
