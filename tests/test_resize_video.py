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


def resize(box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object) -> MediaResult:
    return call("resize_video", box, {"input": src, "output": dst, **extra}, limits)


def size_of(box: Sandbox, name: str) -> tuple[int | None, int | None]:
    stream = describe(box, name).video_streams()[0]
    return stream.width, stream.height


def test_width_only_follows_the_aspect_ratio(media_box: Sandbox) -> None:
    resize(media_box, "clip.mp4", "r.mp4", width=32)
    assert size_of(media_box, "r.mp4") == (32, 24)


def test_height_only_follows_the_aspect_ratio(media_box: Sandbox) -> None:
    resize(media_box, "clip.mp4", "r.mp4", height=24)
    assert size_of(media_box, "r.mp4") == (32, 24)


def test_both_sides_fit_inside_the_box_without_stretching(media_box: Sandbox) -> None:
    resize(media_box, "clip.mp4", "r.mp4", width=100, height=24)
    assert size_of(media_box, "r.mp4") == (32, 24)


def test_frame_rate_is_changed_and_audio_is_kept(media_box: Sandbox) -> None:
    resize(media_box, "clip.mp4", "r.mp4", fps=5)
    info = describe(media_box, "r.mp4")
    assert info.video_streams()[0].fps == 5.0
    assert len(info.audio_streams()) == 1


def test_a_change_is_required(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        resize(media_box, "clip.mp4", "r.mp4")


@pytest.mark.parametrize("extra", [{"width": 1}, {"height": 100_000}, {"fps": 0}, {"fps": 500}])
def test_out_of_range_values_are_rejected(media_box: Sandbox, extra: dict[str, object]) -> None:
    with pytest.raises(InvalidInput):
        resize(media_box, "clip.mp4", "r.mp4", **extra)


def test_audio_only_input_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        resize(media_box, "tone.wav", "r.mp4", width=32)


def test_audio_output_formats_are_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        resize(media_box, "clip.mp4", "r.mp3", width=32)


def test_corrupt_input(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        resize(media_box, "corrupt.mp4", "r.mp4", width=32)
    assert info.value.code is ErrorCode.CORRUPT
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        resize(
            media_box, "clip.mp4", "r.mp4", Limits(timeout_s=60.0, max_media_bytes=100), width=32
        )


@pytest.mark.parametrize("path", ["../clip.mp4", "/etc/passwd"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        resize(media_box, path, "r.mp4", width=32)


@pytest.mark.parametrize("path", ["../r.mp4", "/tmp/r.mp4"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        resize(media_box, "clip.mp4", path, width=32)
