"""All filesystem access goes through a Sandbox bound to one root directory."""

from __future__ import annotations

from pathlib import Path

from toolbelt.core.errors import InvalidInput, SandboxViolation


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
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self._root / candidate
        resolved = candidate.resolve()
        if not str(resolved).startswith(str(self._root)):
            raise SandboxViolation(
                f"path is outside the sandbox: {raw}",
                hint="use a path relative to the sandbox root",
            )
        return resolved

    def display(self, resolved: Path) -> str:
        """Root-relative POSIX form of an already resolved path."""
        relative = resolved.relative_to(self._root).as_posix()
        return relative
