"""Cut a time range out of an audio or video file."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from toolbelt.core.context import Context
from toolbelt.core.errors import InvalidInput
from toolbelt.core.media import MediaProbe
from toolbelt.core.media_formats import AUDIO_OR_VIDEO
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import MediaResult, MediaTransformInput, transcode


class TrimMediaInput(MediaTransformInput):
    output: str = Field(
        description=(
            "File to create. Its extension selects the format. Audio: mp3, m4a, aac, ogg, "
            "opus, flac, wav. Video: mp4, mov, mkv, webm, gif."
        )
    )
    start_s: float = Field(
        default=0.0, ge=0, le=86_400, description="Where the cut begins, in seconds."
    )
    end_s: float | None = Field(
        default=None,
        gt=0,
        le=86_400,
        description="Where the cut ends, in seconds from the start of the input. "
        "Do not combine with duration_s.",
    )
    duration_s: float | None = Field(
        default=None,
        gt=0,
        le=86_400,
        description="Length of the cut in seconds. Do not combine with end_s.",
    )
    stream_copy: bool = Field(
        default=False,
        description=(
            "Copy the streams instead of re-encoding. Much faster and lossless, but the cut "
            "snaps to keyframes and the output must use the same format as the input."
        ),
    )

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.end_s is not None and self.duration_s is not None:
            raise ValueError("give end_s or duration_s, not both")
        if self.end_s is not None and self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        return self


@tool
def trim_media(args: TrimMediaInput, ctx: Context) -> MediaResult:
    """Keep only a time range of an audio or video file.

    Give start_s and either end_s or duration_s. Without both of those the cut runs to
    the end of the input. Disabled unless the sandbox allows writing.
    """

    def seek(info: MediaProbe) -> list[str]:
        if info.duration_s is not None and args.start_s >= info.duration_s:
            raise InvalidInput(
                f"start_s={args.start_s:g} is not before the end of the input "
                f"({info.duration_s:.2f}s)",
                hint="use media_info to see how long the file is",
            )
        return ["-ss", f"{args.start_s:.3f}"] if args.start_s > 0 else []

    length = args.duration_s
    if args.end_s is not None:
        length = args.end_s - args.start_s
    return transcode(
        ctx,
        args,
        kinds=AUDIO_OR_VIDEO,
        input_options=seek,
        output_options=[
            *(["-t", f"{length:.3f}"] if length is not None else []),
            *(["-avoid_negative_ts", "make_zero"] if args.stream_copy else []),
        ],
        stream_copy=args.stream_copy,
    )
