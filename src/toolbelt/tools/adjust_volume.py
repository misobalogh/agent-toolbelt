"""Change or normalize the loudness of audio and video."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from toolbelt.core.context import Context
from toolbelt.core.media_formats import AUDIO_OR_VIDEO
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import MediaResult, MediaTransformInput, Quality, transcode


class AdjustVolumeInput(MediaTransformInput):
    output: str = Field(
        description=(
            "File to create. Its extension selects the format. Audio: mp3, m4a, aac, ogg, "
            "opus, flac, wav. Video: mp4, mov, mkv, webm, gif."
        )
    )
    gain_db: float | None = Field(
        default=None,
        ge=-60,
        le=40,
        description="Change the volume by this many decibels. +6 is about twice as loud.",
    )
    normalize: bool = Field(
        default=False,
        description=(
            "Normalize loudness to -16 LUFS instead of applying a fixed gain. The audio is "
            "resampled to 48 kHz. Do not combine with gain_db."
        ),
    )

    @model_validator(mode="after")
    def _one_mode(self) -> Self:
        if self.normalize == (self.gain_db is not None):
            raise ValueError("give either gain_db or normalize=true")
        return self


@tool
def adjust_volume(args: AdjustVolumeInput, ctx: Context) -> MediaResult:
    """Make audio louder or quieter by a fixed number of dB, or normalize its loudness.

    Works on the first audio stream of audio and video files. A video is re-encoded.
    Disabled unless the sandbox allows writing.
    """
    if args.normalize:
        return transcode(
            ctx,
            args,
            kinds=AUDIO_OR_VIDEO,
            quality=Quality(sample_rate=48000),
            audio_filter="loudnorm=I=-16:TP=-1.5:LRA=11",
            need_audio=True,
        )
    return transcode(
        ctx,
        args,
        kinds=AUDIO_OR_VIDEO,
        audio_filter=f"volume={args.gain_db:.2f}dB",
        need_audio=True,
    )
