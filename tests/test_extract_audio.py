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


def extract(
    box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object
) -> MediaResult:
    return call("extract_audio", box, {"input": src, "output": dst, **extra}, limits)


def test_extracts_the_audio_track_of_a_video(media_box: Sandbox) -> None:
    out = extract(media_box, "clip.mp4", "clip.mp3")
    assert out.format == "mp3"
    info = describe(media_box, "clip.mp3")
    assert info.video_streams() == []
    assert info.duration_s == pytest.approx(2.0, abs=0.3)


def test_options_are_applied(media_box: Sandbox) -> None:
    extract(media_box, "clip.mp4", "clip.wav", sample_rate=16000, channels=1)
    stream = describe(media_box, "clip.wav").audio_streams()[0]
    assert (stream.sample_rate, stream.channels) == (16000, 1)


def test_video_without_audio_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        extract(media_box, "silent.mp4", "out.mp3")
    assert not (media_box.root / "out.mp3").exists()


def test_video_output_formats_are_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        extract(media_box, "clip.mp4", "out.mp4")


def test_corrupt_input(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        extract(media_box, "corrupt.mp4", "out.mp3")
    assert info.value.code is ErrorCode.CORRUPT
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        extract(media_box, "clip.mp4", "out.mp3", Limits(timeout_s=60.0, max_media_bytes=100))


@pytest.mark.parametrize("path", ["../clip.mp4", "/etc/passwd"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        extract(media_box, path, "out.mp3")


@pytest.mark.parametrize("path", ["../out.mp3", "/tmp/out.mp3"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        extract(media_box, "clip.mp4", path)
