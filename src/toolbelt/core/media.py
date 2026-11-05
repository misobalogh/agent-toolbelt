"""The only module that starts a subprocess: ffprobe and ffmpeg.

What keeps this safe:
- The argv is a list, never a shell string.
- Every path is a sandbox-resolved absolute path, so it can be read neither as an
  option (leading dash) nor as a URL (scheme prefix).
- Inputs may only use a short allow-list of demuxers and the `file` protocol.
  Playlist-like formats (hls, concat, sdp) that make ffmpeg open other files fail.
- Callers pass only values they validated (enums, bounded numbers). No raw user
  string ever becomes an option or a filter expression.
- Output goes to a hidden temp file next to the target and is moved into place only
  when ffmpeg succeeded, so a failure or timeout never leaves a partial file.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from toolbelt.core.context import Context
from toolbelt.core.errors import (
    AlreadyExists,
    ErrorCode,
    InvalidInput,
    LimitExceeded,
    ToolError,
    ToolTimeout,
    Unsupported,
)
from toolbelt.core.models import ToolOutput

# Single-file containers and single-image formats only. Playlist and sequence demuxers
# (hls, concat, image2, sdp) are left out on purpose, they open other files.
ALLOWED_DEMUXERS = (
    "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,ogg,wav,mp3,flac,aac,gif,avi,mpegts,flv,asf,ac3,"
    "png_pipe,jpeg_pipe,webp_pipe"
)
_MAX_THREADS = 4
_MAX_ERROR_CHARS = 300

StreamType = Literal["video", "audio", "subtitle", "data", "other"]


class StreamInfo(ToolOutput):
    index: int
    type: StreamType
    codec: str | None
    duration_s: float | None
    bit_rate: int | None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    cover_art: bool = False


class MediaProbe(ToolOutput):
    format_name: str
    duration_s: float | None
    size_bytes: int
    bit_rate: int | None
    streams: list[StreamInfo]

    def video_streams(self) -> list[StreamInfo]:
        """Real video streams, without the cover art that mp3 and m4a files carry."""
        return [s for s in self.streams if s.type == "video" and not s.cover_art]

    def audio_streams(self) -> list[StreamInfo]:
        return [s for s in self.streams if s.type == "audio"]


@dataclass(frozen=True)
class MediaInput:
    path: Path
    options: tuple[str, ...] = ()


def probe(ctx: Context, path: Path) -> MediaProbe:
    """Describe a media file. `path` must come from `Sandbox.input_path`."""
    argv = [
        _binary("ffprobe"),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        *_input_guard(),
        "-i",
        str(path),
    ]
    result = _run(ctx, argv)
    if result.returncode != 0:
        raise ToolError(
            f"not a readable media file: {_last_line(ctx, result.stderr)}",
            hint="the file may be corrupt or in a format that is not supported",
            code=ErrorCode.CORRUPT,
        )
    try:
        return _parse_probe(json.loads(result.stdout))
    except (ValueError, KeyError, TypeError):
        raise ToolError(
            "ffprobe returned output that could not be understood",
            hint="the file may be corrupt",
            code=ErrorCode.CORRUPT,
        ) from None


def run_ffmpeg(
    ctx: Context,
    *,
    inputs: Sequence[MediaInput],
    output: Path,
    muxer: str,
    args: Sequence[str],
    overwrite: bool,
) -> int:
    """Run ffmpeg and move the result to `output`. Return the output size in bytes.

    `output` must come from `Sandbox.output_path`. `muxer` and `args` must be built
    from validated values only.
    """
    argv = [_binary("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-nostats"]
    for item in inputs:
        argv += [*item.options, *_input_guard(), "-i", str(item.path)]
    limit = ctx.limits.max_media_bytes
    temp = _create_temp(output)
    try:
        argv += [
            *args,
            "-threads",
            str(min(_MAX_THREADS, os.cpu_count() or 1)),
            "-fs",
            str(limit),
            "-f",
            muxer,
            "-y",
            str(temp),
        ]
        result = _run(ctx, argv)
        if result.returncode != 0:
            raise _ffmpeg_failure(ctx, result.stderr)
        size = temp.stat().st_size
        if size >= limit:
            raise LimitExceeded(
                f"the result would be at least {limit} bytes, the limit is {limit}",
                hint="shorten or downscale the media, or raise max_media_bytes",
            )
        if size == 0:
            raise ToolError(
                "ffmpeg produced an empty file",
                hint="check that the input has the streams this tool needs",
                code=ErrorCode.CORRUPT,
            )
        _commit(temp, output, overwrite, ctx)
        return size
    finally:
        temp.unlink(missing_ok=True)


def _input_guard() -> list[str]:
    return ["-format_whitelist", ALLOWED_DEMUXERS, "-protocol_whitelist", "file"]


def _binary(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise Unsupported(
            f"{name} is not installed on this machine",
            hint="the operator must install ffmpeg and put it on PATH",
        )
    return found


def _env() -> dict[str, str]:
    env = {"LC_ALL": "C"}
    if "LD_LIBRARY_PATH" in os.environ:
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    return env


def _run(ctx: Context, argv: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=ctx.deadline.remaining(),
            env=_env(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise ToolTimeout(
            "the media operation did not finish in time and was stopped",
            hint="use a shorter or smaller input, or ask the operator to raise timeout_s",
        ) from None
    except OSError as exc:
        raise ToolError(
            f"could not start {Path(argv[0]).name}: {exc.strerror}",
            hint="the operator must check the ffmpeg installation",
        ) from None


def _lines(ctx: Context, stderr: bytes) -> list[str]:
    text = stderr.decode("utf-8", "replace").replace(f"{ctx.sandbox.root}/", "")
    return [line.strip()[:_MAX_ERROR_CHARS] for line in text.splitlines() if line.strip()]


def _last_line(ctx: Context, stderr: bytes) -> str:
    lines = _lines(ctx, stderr)
    return lines[-1] if lines else "no error output"


def _ffmpeg_failure(ctx: Context, stderr: bytes) -> ToolError:
    """Turn ffmpeg's complaints into a structured error.

    The last line is often a consequence ("nothing was written"), so the first
    line that matches a known cause is the one reported.
    """
    lines = _lines(ctx, stderr)

    def first(*markers: str) -> str | None:
        return next((ln for ln in lines if any(m in ln.lower() for m in markers)), None)

    if line := first("invalid data", "moov atom", "end of file"):
        return ToolError(
            f"the input is corrupt or truncated: {line}",
            hint="try another file",
            code=ErrorCode.CORRUPT,
        )
    if line := first("error while opening encoder"):
        return InvalidInput(
            f"the encoder rejected these settings: {line}",
            hint="try a lower audio_bitrate_kbps or another sample_rate",
        )
    if line := first("unknown encoder", "not found", "unsupported"):
        return Unsupported(
            f"this ffmpeg build cannot do that: {line}", hint="try another output format"
        )
    return ToolError(
        f"ffmpeg failed: {lines[-1] if lines else 'no error output'}",
        hint="check the arguments and the input",
    )


def _create_temp(output: Path) -> Path:
    temp = output.parent / f".toolbelt-{secrets.token_hex(8)}.part"
    os.close(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666))
    return temp


def _commit(temp: Path, output: Path, overwrite: bool, ctx: Context) -> None:
    if overwrite:
        os.replace(temp, output)
        return
    shown = ctx.sandbox.display(output)
    try:
        os.link(temp, output)
    except FileExistsError:
        raise AlreadyExists(
            f"file already exists: {shown}", hint="set overwrite to true to replace it"
        ) from None
    except OSError:
        # Hard links are not available on every filesystem.
        if output.exists():
            raise AlreadyExists(
                f"file already exists: {shown}", hint="set overwrite to true to replace it"
            ) from None
        os.rename(temp, output)


def _parse_probe(data: dict[str, Any]) -> MediaProbe:
    fmt = data["format"]
    streams = [_parse_stream(raw) for raw in data.get("streams", [])]
    return MediaProbe(
        format_name=str(fmt["format_name"]),
        duration_s=_number(fmt.get("duration"), float),
        size_bytes=_number(fmt.get("size"), int) or 0,
        bit_rate=_number(fmt.get("bit_rate"), int),
        streams=streams,
    )


def _parse_stream(raw: dict[str, Any]) -> StreamInfo:
    kind = raw.get("codec_type")
    stream_type: StreamType = kind if kind in ("video", "audio", "subtitle", "data") else "other"
    is_video = stream_type == "video"
    return StreamInfo(
        index=int(raw["index"]),
        type=stream_type,
        codec=raw.get("codec_name"),
        duration_s=_number(raw.get("duration"), float),
        bit_rate=_number(raw.get("bit_rate"), int),
        width=_number(raw.get("width"), int) if is_video else None,
        height=_number(raw.get("height"), int) if is_video else None,
        fps=_fps(raw.get("avg_frame_rate")) if is_video else None,
        sample_rate=_number(raw.get("sample_rate"), int) if stream_type == "audio" else None,
        channels=_number(raw.get("channels"), int) if stream_type == "audio" else None,
        cover_art=bool(raw.get("disposition", {}).get("attached_pic", 0)),
    )


def _number[T: (int, float)](value: Any, kind: type[T]) -> T | None:
    try:
        return kind(value)
    except (TypeError, ValueError):
        return None


def _fps(value: Any) -> float | None:
    try:
        num, den = str(value).split("/")
        return round(int(num) / int(den), 3) if int(den) else None
    except ValueError:
        return None
