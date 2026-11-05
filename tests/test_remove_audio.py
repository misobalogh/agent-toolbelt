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


def mute(box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object) -> MediaResult:
    return call("remove_audio", box, {"input": src, "output": dst, **extra}, limits)


def test_result_has_video_and_no_audio(media_box: Sandbox) -> None:
    mute(media_box, "clip.mp4", "mute.mp4")
    info = describe(media_box, "mute.mp4")
    assert len(info.video_streams()) == 1
    assert info.audio_streams() == []


def test_works_for_other_video_formats(media_box: Sandbox) -> None:
    mute(media_box, "clip.mp4", "mute.webm")
    assert describe(media_box, "mute.webm").audio_streams() == []


def test_video_that_is_already_silent_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        mute(media_box, "silent.mp4", "mute.mp4")
    assert not (media_box.root / "mute.mp4").exists()


def test_audio_only_input_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        mute(media_box, "tone.wav", "mute.mp4")


def test_audio_output_formats_are_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        mute(media_box, "clip.mp4", "mute.mp3")


def test_corrupt_input(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        mute(media_box, "corrupt.mp4", "mute.mp4")
    assert info.value.code is ErrorCode.CORRUPT
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        mute(media_box, "clip.mp4", "mute.mp4", Limits(timeout_s=60.0, max_media_bytes=100))


@pytest.mark.parametrize("path", ["../clip.mp4", "/etc/passwd"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        mute(media_box, path, "mute.mp4")


@pytest.mark.parametrize("path", ["../mute.mp4", "/tmp/mute.mp4"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        mute(media_box, "clip.mp4", path)
