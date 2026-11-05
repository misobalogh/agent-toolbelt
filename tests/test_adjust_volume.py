import array
import wave

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


def volume(box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object) -> MediaResult:
    return call("adjust_volume", box, {"input": src, "output": dst, **extra}, limits)


def peak(box: Sandbox, name: str) -> int:
    with wave.open(str(box.root / name)) as handle:
        samples = array.array("h", handle.readframes(handle.getnframes()))
    return max(abs(s) for s in samples)


def test_negative_gain_makes_the_signal_quieter(media_box: Sandbox) -> None:
    volume(media_box, "tone.wav", "quiet.wav", gain_db=-20)
    assert peak(media_box, "quiet.wav") == pytest.approx(peak(media_box, "tone.wav") / 10, rel=0.1)


def test_positive_gain_makes_the_signal_louder(media_box: Sandbox) -> None:
    volume(media_box, "tone.wav", "loud.wav", gain_db=6)
    assert peak(media_box, "loud.wav") == pytest.approx(peak(media_box, "tone.wav") * 2, rel=0.1)


def test_normalize_runs_and_resamples_to_48k(media_box: Sandbox) -> None:
    volume(media_box, "tone.wav", "norm.wav", normalize=True)
    stream = describe(media_box, "norm.wav").audio_streams()[0]
    assert stream.sample_rate == 48000
    assert peak(media_box, "norm.wav") != peak(media_box, "tone.wav")


def test_video_keeps_its_picture(media_box: Sandbox) -> None:
    volume(media_box, "clip.mp4", "out.mp4", gain_db=3)
    info = describe(media_box, "out.mp4")
    assert len(info.video_streams()) == len(info.audio_streams()) == 1


def test_video_without_audio_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        volume(media_box, "silent.mp4", "out.mp4", gain_db=3)


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"gain_db": 3, "normalize": True},
        {"gain_db": 100},
        {"gain_db": -100},
        {"normalize": False},
    ],
)
def test_exactly_one_mode_in_range_is_required(
    media_box: Sandbox, extra: dict[str, object]
) -> None:
    with pytest.raises(InvalidInput):
        volume(media_box, "tone.wav", "out.wav", **extra)


def test_zero_gain_is_a_valid_request(media_box: Sandbox) -> None:
    volume(media_box, "tone.wav", "same.wav", gain_db=0)
    assert peak(media_box, "same.wav") == peak(media_box, "tone.wav")


def test_corrupt_input(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        volume(media_box, "garbage.wav", "out.wav", gain_db=3)
    assert info.value.code is ErrorCode.CORRUPT
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    limits = Limits(timeout_s=60.0, max_media_bytes=100)
    with pytest.raises(LimitExceeded):
        volume(media_box, "clip.mp4", "out.mp4", limits, gain_db=3)


@pytest.mark.parametrize("path", ["../tone.wav", "/etc/passwd"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        volume(media_box, path, "out.wav", gain_db=3)


@pytest.mark.parametrize("path", ["../out.wav", "/tmp/out.wav"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        volume(media_box, "tone.wav", path, gain_db=3)
