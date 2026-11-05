import pytest
from media_helpers import LONG, call, describe, no_leftovers

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import (
    AlreadyExists,
    ErrorCode,
    InvalidInput,
    LimitExceeded,
    SandboxViolation,
    ToolError,
)
from toolbelt.core.limits import Limits
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.media_common import MediaResult


def join(
    box: Sandbox, inputs: list[str], dst: str, limits: Limits = LONG, **extra: object
) -> MediaResult:
    return call("concat_media", box, {"inputs": inputs, "output": dst, **extra}, limits)


def test_joins_audio_files(media_box: Sandbox) -> None:
    join(media_box, ["tone.wav", "tone.wav", "tone.wav"], "all.wav")
    assert describe(media_box, "all.wav").duration_s == pytest.approx(6.0, abs=0.2)


def test_joins_different_audio_formats(media_box: Sandbox) -> None:
    (media_box.root / "a.mp3").write_bytes(b"")
    call("convert_media", media_box, {"input": "tone.wav", "output": "a.mp3", "overwrite": True})
    join(media_box, ["a.mp3", "tone.wav", "clip.mp4"], "all.ogg")
    assert describe(media_box, "all.ogg").duration_s == pytest.approx(6.0, abs=0.4)


def test_joins_videos_with_audio(media_box: Sandbox) -> None:
    join(media_box, ["clip.mp4", "clip.mp4"], "all.mp4")
    info = describe(media_box, "all.mp4")
    assert info.duration_s == pytest.approx(4.0, abs=0.3)
    assert len(info.video_streams()) == len(info.audio_streams()) == 1


def test_clips_of_other_sizes_are_fitted_to_the_first(media_box: Sandbox) -> None:
    call("resize_video", media_box, {"input": "clip.mp4", "output": "big.mp4", "width": 128})
    join(media_box, ["clip.mp4", "big.mp4"], "all.mp4")
    stream = describe(media_box, "all.mp4").video_streams()[0]
    assert (stream.width, stream.height) == (64, 48)


def test_silent_videos_join_into_a_silent_video(media_box: Sandbox) -> None:
    join(media_box, ["silent.mp4", "silent.mp4"], "all.mp4")
    info = describe(media_box, "all.mp4")
    assert info.audio_streams() == []
    assert info.duration_s == pytest.approx(4.0, abs=0.3)


def test_mixed_audio_presence_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput) as info:
        join(media_box, ["clip.mp4", "silent.mp4"], "all.mp4")
    assert "remove_audio" in info.value.hint
    assert not (media_box.root / "all.mp4").exists()


def test_audio_output_needs_audio_in_every_input(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        join(media_box, ["tone.wav", "silent.mp4"], "all.mp3")


def test_video_output_needs_video_in_every_input(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        join(media_box, ["clip.mp4", "tone.wav"], "all.mp4")


def test_at_least_two_inputs_are_required(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        join(media_box, ["tone.wav"], "all.wav")


def test_too_many_inputs_are_rejected(media_box: Sandbox) -> None:
    limits = Limits(timeout_s=60.0, max_media_inputs=2)
    with pytest.raises(LimitExceeded):
        join(media_box, ["tone.wav"] * 3, "all.wav", limits)


def test_unknown_output_format(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        join(media_box, ["tone.wav", "tone.wav"], "all.txt")


def test_corrupt_input_leaves_no_output(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        join(media_box, ["tone.wav", "garbage.wav"], "all.wav")
    assert info.value.code is ErrorCode.CORRUPT
    assert not (media_box.root / "all.wav").exists()
    assert no_leftovers(media_box)


def test_oversized_input(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        join(
            media_box,
            ["clip.mp4", "clip.mp4"],
            "all.mp4",
            Limits(timeout_s=60.0, max_media_bytes=100),
        )


def test_oversized_output(media_box: Sandbox) -> None:
    limits = Limits(timeout_s=60.0, max_media_bytes=60_000)
    with pytest.raises(LimitExceeded):
        join(media_box, ["tone.wav"] * 3, "all.wav", limits)
    assert not (media_box.root / "all.wav").exists()
    assert no_leftovers(media_box)


def test_existing_output_needs_overwrite(media_box: Sandbox) -> None:
    join(media_box, ["tone.wav", "tone.wav"], "all.wav")
    with pytest.raises(AlreadyExists):
        join(media_box, ["tone.wav", "tone.wav"], "all.wav")
    join(media_box, ["tone.wav", "tone.wav"], "all.wav", overwrite=True)


@pytest.mark.parametrize("path", ["../tone.wav", "/etc/passwd"])
def test_input_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        join(media_box, ["tone.wav", path], "all.wav")


@pytest.mark.parametrize("path", ["../all.wav", "/tmp/all.wav"])
def test_output_escape_attempts(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        join(media_box, ["tone.wav", "tone.wav"], path)


def test_read_only_sandbox_refuses(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        join(Sandbox(media_box.root), ["tone.wav", "tone.wav"], "all.wav")
    assert info.value.code is ErrorCode.WRITE_DISABLED
