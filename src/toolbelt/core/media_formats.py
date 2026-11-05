"""Output formats the media tools can write, and the codec settings for each.

Callers pick a format by file extension, never a codec or a raw ffmpeg option, so
the set of things ffmpeg can be asked to do stays small and reviewable.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from toolbelt.core.errors import InvalidInput

FormatKind = Literal["audio", "video", "image"]
AUDIO_ONLY: tuple[FormatKind, ...] = ("audio",)
AUDIO_OR_VIDEO: tuple[FormatKind, ...] = ("audio", "video")
IMAGE_ONLY: tuple[FormatKind, ...] = ("image",)
VIDEO_ONLY: tuple[FormatKind, ...] = ("video",)

# x264 and vp9 reject odd frame sizes in the yuv420p pixel format.
_EVEN_SIZE = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
_GIF_CHAIN = (
    "fps=12,scale='min(480,iw)':-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
)


@dataclass(frozen=True)
class FormatSpec:
    name: str
    muxer: str
    kind: FormatKind
    audio_codec: str | None = None
    audio_kbps: int | None = None  # default bit rate of a lossy codec
    audio_vbr: int | None = None  # default quality scale of a lossy codec, wins over audio_kbps
    video_codec: str | None = None
    crf_default: int | None = None
    video_extra: tuple[str, ...] = ()
    video_filter: str | None = None
    muxer_extra: tuple[str, ...] = ()

    @property
    def lossy_audio(self) -> bool:
        return self.audio_kbps is not None or self.audio_vbr is not None


def _h264(name: str, muxer: str, muxer_extra: tuple[str, ...] = ()) -> FormatSpec:
    return FormatSpec(
        name,
        muxer,
        "video",
        "aac",
        160,
        video_codec="libx264",
        crf_default=23,
        video_extra=("-preset", "veryfast", "-pix_fmt", "yuv420p"),
        video_filter=_EVEN_SIZE,
        muxer_extra=muxer_extra,
    )


_SPECS = (
    FormatSpec("mp3", "mp3", "audio", "libmp3lame", 192),
    FormatSpec("m4a", "ipod", "audio", "aac", 192),
    FormatSpec("aac", "adts", "audio", "aac", 192),
    FormatSpec("ogg", "ogg", "audio", "libvorbis", audio_vbr=5),
    FormatSpec("opus", "opus", "audio", "libopus", 128),
    FormatSpec("flac", "flac", "audio", "flac"),
    FormatSpec("wav", "wav", "audio", "pcm_s16le"),
    _h264("mp4", "mp4", ("-movflags", "+faststart")),
    _h264("mov", "mov"),
    _h264("mkv", "matroska"),
    FormatSpec(
        "webm",
        "webm",
        "video",
        "libopus",
        128,
        video_codec="libvpx-vp9",
        crf_default=32,
        video_extra=("-b:v", "0", "-cpu-used", "4", "-row-mt", "1", "-pix_fmt", "yuv420p"),
        video_filter=_EVEN_SIZE,
    ),
    FormatSpec("gif", "gif", "video", video_codec="gif", video_filter=_GIF_CHAIN),
    FormatSpec(
        "png", "image2", "image", video_codec="png", video_extra=("-frames:v", "1", "-update", "1")
    ),
    FormatSpec(
        "jpg",
        "image2",
        "image",
        video_codec="mjpeg",
        video_extra=("-frames:v", "1", "-update", "1", "-q:v", "3"),
    ),
    FormatSpec("webp", "webp", "image", video_codec="libwebp", video_extra=("-frames:v", "1")),
)

_ALIASES = {"jpeg": "jpg", "matroska": "mkv"}
SPECS_BY_NAME = {spec.name: spec for spec in _SPECS}


def format_for(path: str, kinds: Collection[FormatKind]) -> FormatSpec:
    """Pick the output format from the file extension of `path`."""
    ext = PurePosixPath(path.replace("\\", "/")).suffix.lower().removeprefix(".")
    ext = _ALIASES.get(ext, ext)
    spec = SPECS_BY_NAME.get(ext)
    supported = ", ".join(s.name for s in _SPECS if s.kind in kinds)
    if spec is None or spec.kind not in kinds:
        shown = f".{ext}" if ext else "no extension"
        raise InvalidInput(
            f"this tool cannot write {shown} files: {path}",
            hint=f"end the output name with one of: {supported}",
        )
    return spec
