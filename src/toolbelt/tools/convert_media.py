"""Convert audio and video between formats with ffmpeg."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.media_formats import AUDIO_OR_VIDEO
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import (
    Channels,
    MediaResult,
    MediaTransformInput,
    Quality,
    SampleRate,
    transcode,
)


class ConvertMediaInput(MediaTransformInput):
    output: str = Field(
        description=(
            "File to create. Its extension selects the format. Audio: mp3, m4a, aac, ogg, "
            "opus, flac, wav. Video: mp4, mov, mkv, webm, gif."
        )
    )
    audio_bitrate_kbps: int | None = Field(
        default=None,
        ge=8,
        le=512,
        description="Audio bit rate in kbit/s. Ignored for lossless formats (flac, wav).",
    )
    crf: int | None = Field(
        default=None,
        ge=0,
        le=51,
        description="Video quality, lower is better and larger. Default 23, webm 32.",
    )
    sample_rate: SampleRate | None = Field(default=None, description="Audio sample rate in Hz.")
    channels: Channels | None = Field(default=None, description="1 for mono, 2 for stereo.")


@tool
def convert_media(args: ConvertMediaInput, ctx: Context) -> MediaResult:
    """Convert an audio or video file to another format, chosen by the output extension.

    Converting a video to an audio format keeps only the audio. Video formats keep the
    first video and the first audio stream. Disabled unless the sandbox allows writing.
    """
    return transcode(
        ctx,
        args,
        kinds=AUDIO_OR_VIDEO,
        quality=Quality(args.audio_bitrate_kbps, args.crf, args.sample_rate, args.channels),
    )
