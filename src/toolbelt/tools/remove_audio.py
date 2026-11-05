"""Remove the sound from a video."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.media_formats import VIDEO_ONLY
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import MediaResult, MediaTransformInput, transcode


class RemoveAudioInput(MediaTransformInput):
    output: str = Field(
        description="Video to create. Its extension selects the format: mp4, mov, mkv, webm, gif."
    )


@tool
def remove_audio(args: RemoveAudioInput, ctx: Context) -> MediaResult:
    """Write a copy of a video without its audio track.

    Fails with invalid_input when the input has no audio stream. Disabled unless the
    sandbox allows writing.
    """
    return transcode(ctx, args, kinds=VIDEO_ONLY, drop_audio=True, need_audio=True)
