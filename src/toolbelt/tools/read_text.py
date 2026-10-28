"""Read a text file with encoding detection and truncation info."""

from __future__ import annotations

import codecs

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.errors import InvalidInput, Unsupported
from toolbelt.core.limits import cap
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import tool

BINARY_SNIFF_BYTES = 8192
BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


class ReadTextInput(ToolInput):
    path: str = Field(description="File to read, relative to the sandbox root.")
    encoding: str | None = Field(
        default=None, description="Text encoding. Detected automatically when omitted."
    )
    max_bytes: int | None = Field(
        default=None, description="Maximum bytes to read. Defaults to the configured limit."
    )


class ReadTextOutput(ToolOutput):
    path: str
    text: str
    encoding: str = Field(description="The encoding that was used to decode the text.")
    bytes_read: int
    total_bytes: int
    truncated: bool = Field(description="True when the file is larger than what was read.")


@tool
def read_text(args: ReadTextInput, ctx: Context) -> ReadTextOutput:
    """Read a text file. Large files are cut at max_bytes and flagged as truncated."""
    limit = cap(args.max_bytes, ctx.limits.max_read_bytes, "max_bytes")
    total = ctx.sandbox.stat(args.path).st_size
    with ctx.sandbox.open_read(args.path) as handle:
        data = handle.read(limit)
    encoding = args.encoding or _detect_encoding(data)
    return ReadTextOutput(
        path=ctx.sandbox.display(ctx.sandbox.resolve(args.path)),
        text=_decode(data, encoding),
        encoding=encoding,
        bytes_read=len(data),
        total_bytes=total,
        truncated=total > len(data),
    )


def _detect_encoding(data: bytes) -> str:
    for bom, name in BOMS:
        if data.startswith(bom):
            return name
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        raise Unsupported(
            "file looks binary, not text",
            hint="use file_info to check the type, or a media tool for pdf, image and audio",
        )
    for candidate in ("utf-8", "cp1252"):
        try:
            data.decode(candidate)
        except UnicodeDecodeError:
            continue
        return candidate
    return "latin-1"


def _decode(data: bytes, encoding: str) -> str:
    try:
        return data.decode(encoding, errors="replace")
    except LookupError:
        raise InvalidInput(
            f"unknown encoding: {encoding}", hint="use a Python codec name such as utf-8"
        ) from None
