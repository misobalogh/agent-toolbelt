"""Inspect an audio or video file with ffprobe."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.media import MediaProbe, probe
from toolbelt.core.models import ToolInput
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import media_input


class MediaInfoInput(ToolInput):
    path: str = Field(description="Audio or video file, relative to the sandbox root.")


class MediaInfoOutput(MediaProbe):
    path: str


@tool
def media_info(args: MediaInfoInput, ctx: Context) -> MediaInfoOutput:
    """Describe an audio or video file: container, duration, bit rate and every stream.

    Streams list codec, resolution and frame rate (video) or sample rate and channels
    (audio). Use it before converting or trimming to see what a file contains.
    """
    path = media_input(ctx, args.path)
    info = probe(ctx, path)
    return MediaInfoOutput(path=ctx.sandbox.display(path), **info.model_dump())
