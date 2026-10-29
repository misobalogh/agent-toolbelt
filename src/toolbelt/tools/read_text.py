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
    truncated = total > len(data)
    encoding = args.encoding or _detect_encoding(data, truncated)
    return ReadTextOutput(
        path=ctx.sandbox.display(ctx.sandbox.resolve(args.path)),
        text=_decode(data, encoding, truncated),
        encoding=encoding,
        bytes_read=len(data),
        total_bytes=total,
        truncated=truncated,
    )


def _detect_encoding(data: bytes, truncated: bool) -> str:
    for bom, name in BOMS:
        if data.startswith(bom):
            return name
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        raise Unsupported(
            "file looks binary, not text",
            hint="use file_info to check the type, or a media tool for pdf, image and audio",
        )
    for candidate in ("utf-8", "cp1252"):
        if _decodes_cleanly(data, candidate, truncated):
            return candidate
    return "latin-1"


def _decodes_cleanly(data: bytes, encoding: str, truncated: bool) -> bool:
    # A cut in the middle of a multibyte character is not an error when the
    # file continues past the cut, so a partial tail must not rule out utf-8.
    decoder = codecs.getincrementaldecoder(encoding)()
    try:
        decoder.decode(data, final=not truncated)
    except UnicodeDecodeError:
        return False
    return True


def _decode(data: bytes, encoding: str, truncated: bool) -> str:
    try:
        decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    except LookupError:
        raise InvalidInput(
            f"unknown encoding: {encoding}", hint="use a Python codec name such as utf-8"
        ) from None
    return decoder.decode(data, final=not truncated)
