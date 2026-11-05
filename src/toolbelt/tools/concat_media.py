"""Join several audio or video files one after another."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.errors import InvalidInput, LimitExceeded
from toolbelt.core.media import MediaInput, MediaProbe, StreamInfo, probe, run_ffmpeg
from toolbelt.core.media_formats import AUDIO_OR_VIDEO, FormatSpec, format_for
from toolbelt.core.models import ToolInput
from toolbelt.core.registry import tool
from toolbelt.tools.media_common import MediaResult, Quality, codec_args, media_input


class ConcatMediaInput(ToolInput):
    inputs: list[str] = Field(
        min_length=2,
        description="Files to join in this order, relative to the sandbox root. At least 2.",
    )
    output: str = Field(
        description=(
            "File to create. Its extension selects the format. Audio: mp3, m4a, aac, ogg, "
            "opus, flac, wav. Video: mp4, mov, mkv, webm, gif."
        )
    )
    overwrite: bool = Field(default=False, description="Replace the output if it already exists.")
    create_parents: bool = Field(default=False, description="Create missing parent directories.")


@dataclass(frozen=True)
class _Graph:
    text: str
    video: bool
    audio: bool

    @property
    def labels(self) -> list[str]:
        return [*(["[v]"] if self.video else []), *(["[a]"] if self.audio else [])]


@tool
def concat_media(args: ConcatMediaInput, ctx: Context) -> MediaResult:
    """Join audio files or video files into one file, in the given order.

    Everything is re-encoded, so the inputs may differ in format. For video, every clip
    is scaled to fit the size and frame rate of the first one. All inputs must have audio,
    or none of them. Disabled unless the sandbox allows writing.
    """
    maximum = ctx.limits.max_media_inputs
    if len(args.inputs) > maximum:
        raise LimitExceeded(
            f"{len(args.inputs)} inputs given, the limit is {maximum}",
            hint="join the files in several steps",
        )
    spec = format_for(args.output, AUDIO_OR_VIDEO)
    paths = [media_input(ctx, raw) for raw in args.inputs]
    graph = _build_graph(spec, [probe(ctx, path) for path in paths])
    target = ctx.sandbox.output_path(
        args.output, overwrite=args.overwrite, create_parents=args.create_parents
    )
    size = run_ffmpeg(
        ctx,
        inputs=[MediaInput(path) for path in paths],
        output=target,
        muxer=spec.muxer,
        args=[
            "-filter_complex",
            graph.text,
            *[item for label in graph.labels for item in ("-map", label)],
            *codec_args(spec, Quality(), video=graph.video, audio=graph.audio),
        ],
        overwrite=args.overwrite,
    )
    return MediaResult(path=ctx.sandbox.display(target), format=spec.name, size_bytes=size)


def _build_graph(spec: FormatSpec, infos: list[MediaProbe]) -> _Graph:
    """Filter graph that brings every input to one format and joins them.

    Built from numbers taken from ffprobe and from constants only.
    """
    video = spec.kind == "video"
    audio = False
    if spec.audio_codec is not None:
        has_audio = [bool(info.audio_streams()) for info in infos]
        if spec.kind == "audio" and not all(has_audio):
            raise InvalidInput(
                "every input needs an audio stream", hint="use media_info to check the inputs"
            )
        if any(has_audio) and not all(has_audio):
            raise InvalidInput(
                "some inputs have audio and some do not",
                hint="use remove_audio on the others, or join files that all have audio",
            )
        audio = all(has_audio)

    parts: list[str] = []
    segments: list[str] = []
    if video:
        reference = _first_video(infos[0])
        width = (reference.width or 0) // 2 * 2
        height = (reference.height or 0) // 2 * 2
        if not width or not height:
            raise InvalidInput("cannot read the video size of the first input")
        fps = min(60, max(1, round(reference.fps or 25)))
    if audio:
        first_audio = infos[0].audio_streams()[0]
        rate = first_audio.sample_rate or 48000
        layout = "mono" if first_audio.channels == 1 else "stereo"
    for number, info in enumerate(infos):
        if video:
            parts.append(
                f"[{number}:{_first_video(info).index}]"
                f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{number}]"
            )
            segments.append(f"[v{number}]")
        if audio:
            parts.append(
                f"[{number}:{info.audio_streams()[0].index}]"
                f"aformat=sample_rates={rate}:channel_layouts={layout}[a{number}]"
            )
            segments.append(f"[a{number}]")
    outputs = ("[vc]" if video else "") + ("[a]" if audio else "")
    parts.append(f"{''.join(segments)}concat=n={len(infos)}:v={int(video)}:a={int(audio)}{outputs}")
    if video:
        parts.append(f"[vc]{spec.video_filter or 'null'}[v]")
    return _Graph(";".join(parts), video, audio)


def _first_video(info: MediaProbe) -> StreamInfo:
    streams = info.video_streams()
    if not streams:
        raise InvalidInput(
            "an input has no video stream", hint="use media_info to check the inputs"
        )
    return streams[0]
