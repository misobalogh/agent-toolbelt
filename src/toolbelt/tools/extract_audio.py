"""Pull the audio track out of a video file."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.media_formats import AUDIO_ONLY
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import (
    Channels,
    MediaResult,
    MediaTransformInput,
    Quality,
    SampleRate,
    transcode,
)


class ExtractAudioInput(MediaTransformInput):
    output: str = Field(
        description=(
            "Audio file to create. Its extension selects the format: "
            "mp3, m4a, aac, ogg, opus, flac, wav."
        )
    )
    audio_bitrate_kbps: int | None = Field(
        default=None,
        ge=8,
        le=512,
        description="Audio bit rate in kbit/s. Ignored for lossless formats (flac, wav).",
    )
    sample_rate: SampleRate | None = Field(default=None, description="Audio sample rate in Hz.")
    channels: Channels | None = Field(default=None, description="1 for mono, 2 for stereo.")


@tool
def extract_audio(args: ExtractAudioInput, ctx: Context) -> MediaResult:
    """Extract the first audio stream of a video (or audio) file into an audio file.

    Fails with invalid_input when the input has no audio stream. Disabled unless the
    sandbox allows writing.
    """
    return transcode(
        ctx,
        args,
        kinds=AUDIO_ONLY,
        quality=Quality(args.audio_bitrate_kbps, None, args.sample_rate, args.channels),
    )
