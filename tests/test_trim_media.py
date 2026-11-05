import pytest
from media_helpers import LONG, call, describe, no_leftovers

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import (
    ErrorCode,
    InvalidInput,
    LimitExceeded,
    SandboxViolation,
    ToolError,
)
from toolbelt.core.limits import Limits
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.media_common import MediaResult


def trim(box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object) -> MediaResult:
    return call("trim_media", box, {"input": src, "output": dst, **extra}, limits)


def test_keeps_the_requested_duration_of_audio(media_box: Sandbox) -> None:
    trim(media_box, "tone.wav", "cut.wav", start_s=0.5, duration_s=1.0)
    assert describe(media_box, "cut.wav").duration_s == pytest.approx(1.0, abs=0.1)


def test_end_s_is_measured_from_the_start_of_the_input(media_box: Sandbox) -> None:
    trim(media_box, "tone.wav", "cut.wav", start_s=0.5, end_s=1.25)
    assert describe(media_box, "cut.wav").duration_s == pytest.approx(0.75, abs=0.1)


def test_without_an_end_the_cut_runs_to_the_end(media_box: Sandbox) -> None:
    trim(media_box, "tone.wav", "cut.wav", start_s=1.5)
    assert describe(media_box, "cut.wav").duration_s == pytest.approx(0.5, abs=0.1)


def test_trims_video_with_both_streams(media_box: Sandbox) -> None:
    trim(media_box, "clip.mp4", "cut.mp4", start_s=0.5, duration_s=1.0)
    info = describe(media_box, "cut.mp4")
    assert info.duration_s == pytest.approx(1.0, abs=0.2)
    assert len(info.video_streams()) == len(info.audio_streams()) == 1


def test_stream_copy_keeps_the_codecs(media_box: Sandbox) -> None:
    trim(media_box, "clip.mp4", "cut.mp4", start_s=0.0, duration_s=1.0, stream_copy=True)
    info = describe(media_box, "cut.mp4")
    assert info.video_streams()[0].codec == "h264"
    assert info.audio_streams()[0].codec == "aac"


def test_start_past_the_end_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput) as info:
        trim(media_box, "tone.wav", "cut.wav", start_s=5)
    assert "media_info" in info.value.hint
    assert not (media_box.root / "cut.wav").exists()


@pytest.mark.parametrize(
    "extra",
    [
        {"end_s": 1.0, "duration_s": 1.0},
        {"start_s": 1.0, "end_s": 1.0},
        {"start_s": 2.0, "end_s": 1.0},
        {"start_s": -1},
        {"duration_s": 0},
        {"duration_s": 1e9},
    ],
)
def test_bad_ranges_are_rejected(media_box: Sandbox, extra: dict[str, object]) -> None:
    with pytest.raises(InvalidInput):
        trim(media_box, "tone.wav", "cut.wav", **extra)


@pytest.mark.parametrize("name", ["corrupt.mp4", "garbage.wav", "evil.m3u8"])
def test_corrupt_input(media_box: Sandbox, name: str) -> None:
    with pytest.raises(ToolError) as info:
        trim(media_box, name, "cut.mp3", duration_s=1)
    assert info.value.code is ErrorCode.CORRUPT
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        trim(media_box, "clip.mp4", "cut.mp4", Limits(timeout_s=60.0, max_media_bytes=100))


@pytest.mark.parametrize("path", ["../clip.mp4", "/etc/passwd", "a/../../clip.mp4"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        trim(media_box, path, "cut.mp4")


@pytest.mark.parametrize("path", ["../cut.mp4", "/tmp/cut.mp4"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        trim(media_box, "clip.mp4", path)


def test_read_only_sandbox_refuses(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        trim(Sandbox(media_box.root), "tone.wav", "cut.wav", duration_s=1)
    assert info.value.code is ErrorCode.WRITE_DISABLED
