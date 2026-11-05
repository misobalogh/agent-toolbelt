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
from toolbelt.tools.change_speed import _atempo_chain
from toolbelt.tools.media_common import MediaResult


def speed(box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object) -> MediaResult:
    return call("change_speed", box, {"input": src, "output": dst, **extra}, limits)


@pytest.mark.parametrize(("factor", "expected"), [(2.0, 1.0), (0.5, 4.0), (4.0, 0.5), (0.25, 8.0)])
def test_audio_duration_scales_with_the_factor(
    media_box: Sandbox, factor: float, expected: float
) -> None:
    speed(media_box, "tone.wav", "out.wav", factor=factor)
    assert describe(media_box, "out.wav").duration_s == pytest.approx(expected, abs=0.25)


def test_video_and_audio_follow_the_factor(media_box: Sandbox) -> None:
    speed(media_box, "clip.mp4", "out.mp4", factor=2)
    info = describe(media_box, "out.mp4")
    assert info.duration_s == pytest.approx(1.0, abs=0.25)
    assert len(info.video_streams()) == len(info.audio_streams()) == 1


def test_silent_video_can_be_sped_up(media_box: Sandbox) -> None:
    speed(media_box, "silent.mp4", "out.mp4", factor=2)
    assert describe(media_box, "out.mp4").duration_s == pytest.approx(1.0, abs=0.25)


@pytest.mark.parametrize(
    ("factor", "stages"), [(1.0, 1), (2.0, 1), (0.5, 1), (3.0, 2), (4.0, 2), (0.25, 2)]
)
def test_atempo_stages_stay_in_the_supported_range(factor: float, stages: int) -> None:
    chain = _atempo_chain(factor).split(",")
    assert len(chain) == stages
    product = 1.0
    for stage in chain:
        value = float(stage.removeprefix("atempo="))
        assert 0.5 <= value <= 2.0
        product *= value
    assert product == pytest.approx(factor, rel=1e-5)


@pytest.mark.parametrize("factor", [0, -1, 0.1, 5, 100])
def test_factor_out_of_range_is_rejected(media_box: Sandbox, factor: float) -> None:
    with pytest.raises(InvalidInput):
        speed(media_box, "tone.wav", "out.wav", factor=factor)


def test_factor_is_required(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        speed(media_box, "tone.wav", "out.wav")


def test_corrupt_input(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        speed(media_box, "garbage.wav", "out.wav", factor=2)
    assert info.value.code is ErrorCode.CORRUPT
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    limits = Limits(timeout_s=60.0, max_media_bytes=100)
    with pytest.raises(LimitExceeded):
        speed(media_box, "clip.mp4", "out.mp4", limits, factor=2)


def test_oversized_output(media_box: Sandbox) -> None:
    limits = Limits(timeout_s=60.0, max_media_bytes=60_000)
    with pytest.raises(LimitExceeded):
        speed(media_box, "tone.wav", "out.wav", limits, factor=0.25)
    assert not (media_box.root / "out.wav").exists()
    assert no_leftovers(media_box)


@pytest.mark.parametrize("path", ["../tone.wav", "/etc/passwd"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        speed(media_box, path, "out.wav", factor=2)


@pytest.mark.parametrize("path", ["../out.wav", "/tmp/out.wav"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        speed(media_box, "tone.wav", path, factor=2)
