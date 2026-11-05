import pytest

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import (
    ErrorCode,
    LimitExceeded,
    NotFound,
    SandboxViolation,
    ToolError,
)
from toolbelt.core.limits import Limits
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.media_info import MediaInfoOutput


def run(box: Sandbox, path: str, limits: Limits | None = None) -> MediaInfoOutput:
    result = default_registry.call("media_info", {"path": path}, box, limits)
    assert isinstance(result, MediaInfoOutput)
    return result


def test_describes_an_audio_file(media_box: Sandbox) -> None:
    out = run(media_box, "tone.wav")
    assert out.path == "tone.wav"
    assert out.format_name == "wav"
    assert out.duration_s == pytest.approx(2.0, abs=0.1)
    assert out.video_streams() == []
    assert out.audio_streams()[0].sample_rate == 22050


def test_describes_a_video_file(media_box: Sandbox) -> None:
    out = run(media_box, "clip.mp4")
    assert len(out.video_streams()) == 1
    assert len(out.audio_streams()) == 1
    assert out.size_bytes == (media_box.root / "clip.mp4").stat().st_size


def test_works_in_a_read_only_sandbox(media_box: Sandbox) -> None:
    run(Sandbox(media_box.root), "tone.wav")


@pytest.mark.parametrize("name", ["corrupt.mp4", "garbage.wav", "evil.m3u8"])
def test_corrupt_input_is_a_structured_error(media_box: Sandbox, name: str) -> None:
    with pytest.raises(ToolError) as info:
        run(media_box, name)
    assert info.value.code is ErrorCode.CORRUPT


def test_oversized_input_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        run(media_box, "clip.mp4", Limits(max_media_bytes=100))


def test_missing_file(media_box: Sandbox) -> None:
    with pytest.raises(NotFound):
        run(media_box, "nope.mp4")


@pytest.mark.parametrize("path", ["../clip.mp4", "/etc/passwd", "a/../../clip.mp4"])
def test_escape_attempts_are_rejected(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        run(media_box, path)
