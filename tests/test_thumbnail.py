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


def shot(box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object) -> MediaResult:
    return call("thumbnail", box, {"input": src, "output": dst, **extra}, limits)


@pytest.mark.parametrize(
    ("name", "codec"), [("f.png", "png"), ("f.jpg", "mjpeg"), ("f.webp", "webp")]
)
def test_saves_a_frame_in_each_image_format(media_box: Sandbox, name: str, codec: str) -> None:
    out = shot(media_box, "clip.mp4", name)
    assert out.size_bytes > 0
    stream = describe(media_box, name).video_streams()[0]
    assert (stream.codec, stream.width, stream.height) == (codec, 64, 48)


def test_width_keeps_the_aspect_ratio(media_box: Sandbox) -> None:
    shot(media_box, "clip.mp4", "f.png", width=32)
    stream = describe(media_box, "f.png").video_streams()[0]
    assert (stream.width, stream.height) == (32, 24)


def test_a_chosen_moment_gives_a_different_frame(media_box: Sandbox) -> None:
    shot(media_box, "clip.mp4", "early.png", at_s=0.0)
    shot(media_box, "clip.mp4", "late.png", at_s=1.5)
    assert (media_box.root / "early.png").read_bytes() != (media_box.root / "late.png").read_bytes()


def test_a_moment_past_the_end_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        shot(media_box, "clip.mp4", "f.png", at_s=30)
    assert not (media_box.root / "f.png").exists()


def test_audio_only_input_has_no_frame(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        shot(media_box, "tone.wav", "f.png")


@pytest.mark.parametrize("name", ["f.mp3", "f.mp4", "f.gif", "f.bmp"])
def test_only_image_formats_are_accepted(media_box: Sandbox, name: str) -> None:
    with pytest.raises(InvalidInput):
        shot(media_box, "clip.mp4", name)


def test_width_out_of_range_is_rejected(media_box: Sandbox) -> None:
    for width in (0, 8, 100_000):
        with pytest.raises(InvalidInput):
            shot(media_box, "clip.mp4", "f.png", width=width)


def test_corrupt_input(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        shot(media_box, "corrupt.mp4", "f.png")
    assert info.value.code is ErrorCode.CORRUPT
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        shot(media_box, "clip.mp4", "f.png", Limits(timeout_s=60.0, max_media_bytes=100))


@pytest.mark.parametrize("path", ["../clip.mp4", "/etc/passwd"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        shot(media_box, path, "f.png")


@pytest.mark.parametrize("path", ["../f.png", "/tmp/f.png"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        shot(media_box, "clip.mp4", path)
