"""Save one frame of a video as an image."""

from __future__ import annotations

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.errors import InvalidInput
from toolbelt.core.media import MediaProbe
from toolbelt.core.media_formats import IMAGE_ONLY
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import MediaResult, MediaTransformInput, transcode


class ThumbnailInput(MediaTransformInput):
    output: str = Field(
        description="Image to create. Its extension selects the format: png, jpg, webp."
    )
    at_s: float | None = Field(
        default=None,
        ge=0,
        le=86_400,
        description="Time of the frame in seconds. Default: the middle of the video.",
    )
    width: int | None = Field(
        default=None,
        ge=16,
        le=4096,
        description="Scale the image to this width in pixels, keeping the aspect ratio.",
    )


@tool
def thumbnail(args: ThumbnailInput, ctx: Context) -> MediaResult:
    """Save a single frame of a video as a png, jpg or webp image.

    Disabled unless the sandbox allows writing.
    """

    def seek(info: MediaProbe) -> list[str]:
        moment = args.at_s
        if info.duration_s is None:
            return ["-ss", f"{moment or 0.0:.3f}"]
        if moment is None:
            moment = info.duration_s / 2
        elif moment >= info.duration_s:
            raise InvalidInput(
                f"at_s={moment:g} is not before the end of the video ({info.duration_s:.2f}s)",
                hint="use a smaller at_s or leave it out for the middle frame",
            )
        return ["-ss", f"{moment:.3f}"]

    return transcode(
        ctx,
        args,
        kinds=IMAGE_ONLY,
        video_filter=f"scale={args.width}:-2" if args.width else None,
        input_options=seek,
    )
