"""Speed up or slow down audio and video."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.media_formats import AUDIO_OR_VIDEO
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import MediaResult, MediaTransformInput, transcode


class ChangeSpeedInput(MediaTransformInput):
    output: str = Field(
        description=(
            "File to create. Its extension selects the format. Audio: mp3, m4a, aac, ogg, "
            "opus, flac, wav. Video: mp4, mov, mkv, webm, gif."
        )
    )
    factor: float = Field(
        ge=0.25,
        le=4.0,
        description="Playback speed. 2 is twice as fast, 0.5 is half speed. Pitch is kept.",
    )


@tool
def change_speed(args: ChangeSpeedInput, ctx: Context) -> MediaResult:
    """Change the playback speed of an audio or video file without changing the pitch.

    The result is shorter for factor > 1 and longer for factor < 1. Disabled unless the
    sandbox allows writing.
    """
    return transcode(
        ctx,
        args,
        kinds=AUDIO_OR_VIDEO,
        video_filter=f"setpts=PTS/{args.factor:.6f}",
        audio_filter=_atempo_chain(args.factor),
    )


def _atempo_chain(factor: float) -> str:
    """atempo accepts 0.5 to 2.0 per stage, so a larger change needs two stages."""
    if factor > 2.0:
        return f"atempo=2.0,atempo={factor / 2.0:.6f}"
    if factor < 0.5:
        return f"atempo=0.5,atempo={factor / 0.5:.6f}"
    return f"atempo={factor:.6f}"
