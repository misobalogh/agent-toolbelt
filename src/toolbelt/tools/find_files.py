"""Find files by glob pattern."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.limits import cap
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import tool


class FindFilesInput(ToolInput):
    pattern: str = Field(description="Glob pattern such as '*.pdf' or '**/*.md'.")
    path: str = Field(default=".", description="Directory to search from, relative to the root.")
    max_results: int | None = Field(
        default=None, description="Maximum matches to return. Defaults to the configured limit."
    )


class FoundFile(ToolOutput):
    path: str
    size: int


class FindFilesOutput(ToolOutput):
    matches: list[FoundFile]
    truncated: bool = Field(description="True when more files matched than were returned.")


@tool
def find_files(args: FindFilesInput, ctx: Context) -> FindFilesOutput:
    """Find regular files below a directory that match a glob pattern, sorted by path."""
    limit = cap(args.max_results, ctx.limits.max_entries, "max_results")
    found = []
    for entry in ctx.sandbox.glob(args.path, args.pattern):
        ctx.deadline.check()
        found.append(FoundFile(path=entry.path, size=entry.size))
    found.sort(key=lambda f: f.path)
    return FindFilesOutput(matches=found[:limit], truncated=len(found) > limit)
