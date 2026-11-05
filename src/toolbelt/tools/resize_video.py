"""Scale a video and optionally change its frame rate."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from toolbelt.core.context import Context
from toolbelt.core.media_formats import VIDEO_ONLY
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import MediaResult, MediaTransformInput, Quality, transcode


class ResizeVideoInput(MediaTransformInput):
    output: str = Field(
        description="Video to create. Its extension selects the format: mp4, mov, mkv, webm, gif."
    )
    width: int | None = Field(default=None, ge=16, le=7680, description="Target width in pixels.")
    height: int | None = Field(default=None, ge=16, le=7680, description="Target height in pixels.")
    fps: int | None = Field(default=None, ge=1, le=60, description="Target frames per second.")
    crf: int | None = Field(
        default=None, ge=0, le=51, description="Video quality, lower is better and larger."
    )

    @model_validator(mode="after")
    def _needs_a_change(self) -> Self:
        if self.width is None and self.height is None and self.fps is None:
            raise ValueError("give at least one of width, height and fps")
        return self


@tool
def resize_video(args: ResizeVideoInput, ctx: Context) -> MediaResult:
    """Scale a video to a new size and/or frame rate, keeping the aspect ratio.

    With only width or only height the other side follows the aspect ratio. With both, the
    video is scaled to fit inside that box and is never stretched. Disabled unless the
    sandbox allows writing.
    """
    filters = []
    if args.width and args.height:
        filters.append(f"scale=w={args.width}:h={args.height}:force_original_aspect_ratio=decrease")
    elif args.width:
        filters.append(f"scale={args.width}:-2")
    elif args.height:
        filters.append(f"scale=-2:{args.height}")
    if args.fps:
        filters.append(f"fps={args.fps}")
    return transcode(
        ctx,
        args,
        kinds=VIDEO_ONLY,
        quality=Quality(crf=args.crf),
        video_filter=",".join(filters),
    )
