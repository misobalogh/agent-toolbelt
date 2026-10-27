"""Basic metadata about a file or directory."""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import tool
from toolbelt.core.sandbox import EntryKind, kind_of


class FileInfoInput(ToolInput):
    path: str = Field(description="File or directory, relative to the sandbox root.")


class FileInfoOutput(ToolOutput):
    path: str
    kind: EntryKind
    size: int = Field(description="Size in bytes.")
    modified: datetime = Field(description="Last modification time in UTC.")
    mime_type: str | None = Field(description="Guessed from the file name, not the content.")


@tool
def file_info(args: FileInfoInput, ctx: Context) -> FileInfoOutput:
    """Return the kind, size, modification time and guessed MIME type of a path."""
    info = ctx.sandbox.stat(args.path)
    resolved = ctx.sandbox.resolve(args.path)
    return FileInfoOutput(
        path=ctx.sandbox.display(resolved),
        kind=kind_of(info.st_mode),
        size=info.st_size,
        modified=datetime.fromtimestamp(info.st_mtime, tz=UTC),
        mime_type=mimetypes.guess_type(resolved.name)[0],
    )
