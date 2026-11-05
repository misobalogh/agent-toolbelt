"""Pieces shared by the media tools."""

from __future__ import annotations

from pathlib import Path

from toolbelt.core.context import Context
from toolbelt.core.errors import LimitExceeded


def media_input(ctx: Context, raw: str) -> Path:
    """Resolve an input file and refuse one above `max_media_bytes`."""
    path = ctx.sandbox.input_path(raw)
    size = path.stat().st_size
    if size > ctx.limits.max_media_bytes:
        raise LimitExceeded(
            f"{raw} is {size} bytes, the limit is {ctx.limits.max_media_bytes}",
            hint="use a smaller file or ask the operator to raise max_media_bytes",
        )
    return path
