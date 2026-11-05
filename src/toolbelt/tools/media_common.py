"""Pieces shared by the media tools."""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.errors import InvalidInput, LimitExceeded
from toolbelt.core.media import MediaInput, MediaProbe, StreamInfo, probe, run_ffmpeg
from toolbelt.core.media_formats import FormatKind, FormatSpec, format_for
from toolbelt.core.models import ToolInput, ToolOutput

SampleRate = Literal[8000, 16000, 22050, 24000, 32000, 44100, 48000]
Channels = Literal[1, 2]


def media_input(ctx: Context, raw: str) -> Path:
    """Resolve an input file and refuse one above `max_media_bytes`."""
    path = ctx.sandbox.input_path(raw)
    size = path.stat().st_size
    if size > ctx.limits.max_media_bytes:
        raise LimitExceeded(
            f"{raw} is {size} bytes, the limit is {ctx.limits.max_media_bytes}",
            hint="use a smaller file or ask the operator to raise max_media_bytes",
        )
    return path


class MediaTransformInput(ToolInput):
    """Fields shared by every tool that reads one media file and writes another."""

    input: str = Field(description="Source file, relative to the sandbox root.")
    output: str = Field(description="File to create. Its extension selects the format.")
    overwrite: bool = Field(default=False, description="Replace the output if it already exists.")
    create_parents: bool = Field(default=False, description="Create missing parent directories.")


class MediaResult(ToolOutput):
    path: str
    format: str
    size_bytes: int


@dataclass(frozen=True)
class Quality:
    audio_kbps: int | None = None
    crf: int | None = None
    sample_rate: int | None = None
    channels: int | None = None


def transcode(
    ctx: Context,
    args: MediaTransformInput,
    *,
    kinds: Collection[FormatKind],
    quality: Quality | None = None,
    video_filter: str | None = None,
    audio_filter: str | None = None,
    input_options: Sequence[str] | Callable[[MediaProbe], Sequence[str]] = (),
    output_options: Sequence[str] = (),
    drop_audio: bool = False,
    need_audio: bool = False,
    stream_copy: bool = False,
) -> MediaResult:
    """Read `args.input`, write `args.output` in the format its extension names.

    The first real video stream and the first audio stream are used. Filters are
    applied only to a stream that ends up in the output. `input_options` may be a
    function of the probe result, which lets a tool reject a request that does not fit
    the input (a start time past the end) before anything is written.
    """
    spec = format_for(args.output, kinds)
    source = media_input(ctx, args.input)
    info = probe(ctx, source)
    leading = input_options(info) if callable(input_options) else input_options
    chosen = _select_streams(info, spec, drop_audio=drop_audio, need_audio=need_audio)
    target = ctx.sandbox.output_path(
        args.output, overwrite=args.overwrite, create_parents=args.create_parents
    )
    out: list[str] = []
    for stream in chosen:
        out += ["-map", f"0:{stream.index}"]
    has_video = any(s.type == "video" for s in chosen)
    has_audio = any(s.type == "audio" for s in chosen)
    if stream_copy:
        out += ["-c", "copy", *spec.muxer_extra]
    else:
        filters = [f for f in (video_filter, spec.video_filter) if f and has_video]
        if filters:
            out += ["-vf", ",".join(filters)]
        if audio_filter and has_audio:
            out += ["-af", audio_filter]
        out += codec_args(spec, quality or Quality(), video=has_video, audio=has_audio)
    size = run_ffmpeg(
        ctx,
        inputs=[MediaInput(source, tuple(leading))],
        output=target,
        muxer=spec.muxer,
        args=[*out, *output_options],
        overwrite=args.overwrite,
    )
    return MediaResult(path=ctx.sandbox.display(target), format=spec.name, size_bytes=size)


def _select_streams(
    info: MediaProbe, spec: FormatSpec, *, drop_audio: bool, need_audio: bool
) -> list[StreamInfo]:
    video = info.video_streams()
    audio = info.audio_streams()
    if need_audio and not audio:
        raise InvalidInput(
            "the input has no audio stream", hint="use media_info to see which streams it has"
        )
    if spec.kind == "audio":
        if not audio:
            raise InvalidInput(
                "the input has no audio stream", hint="use media_info to see which streams it has"
            )
        return [audio[0]]
    if not video:
        raise InvalidInput(
            "the input has no video stream", hint="use media_info to see which streams it has"
        )
    keep_audio = spec.audio_codec is not None and not drop_audio and bool(audio)
    return [video[0], audio[0]] if keep_audio else [video[0]]


def codec_args(spec: FormatSpec, quality: Quality, *, video: bool, audio: bool) -> list[str]:
    """Codec, quality and container settings for the streams that are written."""
    out: list[str] = []
    if video:
        out += ["-c:v", str(spec.video_codec)]
        if spec.crf_default is not None:
            crf = spec.crf_default if quality.crf is None else quality.crf
            out += ["-crf", str(crf)]
        out += spec.video_extra
    if audio:
        out += ["-c:a", str(spec.audio_codec)]
        if spec.lossy_audio:
            if quality.audio_kbps is None and spec.audio_vbr is not None:
                out += ["-q:a", str(spec.audio_vbr)]
            else:
                out += ["-b:a", f"{quality.audio_kbps or spec.audio_kbps}k"]
        if quality.sample_rate is not None:
            out += ["-ar", str(quality.sample_rate)]
        if quality.channels is not None:
            out += ["-ac", str(quality.channels)]
    return [*out, *spec.muxer_extra]
