"""Write a UTF-8 text file. Only works when the sandbox allows writing."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.errors import LimitExceeded
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import tool


class WriteTextInput(ToolInput):
    path: str = Field(description="File to write, relative to the sandbox root.")
    text: str = Field(description="Content to write, encoded as UTF-8.")
    overwrite: bool = Field(default=False, description="Replace the file if it already exists.")
    create_parents: bool = Field(default=False, description="Create missing parent directories.")


class WriteTextOutput(ToolOutput):
    path: str
    bytes_written: int


@tool
def write_text(args: WriteTextInput, ctx: Context) -> WriteTextOutput:
    """Write text to a file. Disabled unless the operator enabled writing for the sandbox."""
    data = args.text.encode("utf-8")
    if len(data) > ctx.limits.max_write_bytes:
        raise LimitExceeded(
            f"text is {len(data)} bytes, the limit is {ctx.limits.max_write_bytes}",
            hint="split the content over several files",
        )
    with ctx.sandbox.open_write(
        args.path, overwrite=args.overwrite, create_parents=args.create_parents
    ) as handle:
        handle.write(data)
    return WriteTextOutput(
        path=ctx.sandbox.display(ctx.sandbox.resolve(args.path)), bytes_written=len(data)
    )
