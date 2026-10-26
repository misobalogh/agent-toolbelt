"""List the contents of a directory."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.limits import cap
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import tool
from toolbelt.core.sandbox import EntryKind


class ListDirInput(ToolInput):
    path: str = Field(default=".", description="Directory to list, relative to the sandbox root.")
    include_hidden: bool = Field(default=False, description="Include names starting with a dot.")
    max_entries: int | None = Field(
        default=None, description="Maximum entries to return. Defaults to the configured limit."
    )


class DirEntry(ToolOutput):
    name: str
    path: str
    kind: EntryKind
    size: int


class ListDirOutput(ToolOutput):
    path: str
    entries: list[DirEntry]
    truncated: bool = Field(description="True when more entries exist than were returned.")


@tool
def list_dir(args: ListDirInput, ctx: Context) -> ListDirOutput:
    """List the files and directories directly inside a directory."""
    limit = cap(args.max_entries, ctx.limits.max_entries, "max_entries")
    entries = [
        e
        for e in ctx.sandbox.list_dir(args.path)
        if args.include_hidden or not e.name.startswith(".")
    ]
    shown = entries[:limit]
    return ListDirOutput(
        path=ctx.sandbox.display(ctx.sandbox.resolve(args.path)),
        entries=[DirEntry(name=e.name, path=e.path, kind=e.kind, size=e.size) for e in shown],
        truncated=len(entries) > limit,
    )
