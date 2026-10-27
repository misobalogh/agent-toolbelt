"""All filesystem access goes through a Sandbox bound to one root directory."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from toolbelt.core.errors import (
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
    def __init__(self, root: str | Path) -> None:
        resolved = Path(root).resolve()
        if not resolved.is_dir():
            raise InvalidInput(f"sandbox root is not a directory: {root}")
        self._root = resolved

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


def _missing(raw: str) -> NotFound:
    return NotFound(f"no such file or directory: {raw}", hint="use list_dir to find valid paths")


def _denied(raw: str) -> PermissionDenied:
    return PermissionDenied(f"permission denied: {raw}", hint="choose a different path")
