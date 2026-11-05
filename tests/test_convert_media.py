import pytest
from media_helpers import LONG, call, describe, no_leftovers

import toolbelt.tools  # noqa: F401
from toolbelt.core.errors import (
    AlreadyExists,
    ErrorCode,
    InvalidInput,
    LimitExceeded,
    NotFound,
    SandboxViolation,
    ToolError,
)
from toolbelt.core.limits import Limits
from toolbelt.core.sandbox import Sandbox


def convert(box: Sandbox, src: str, dst: str, limits: Limits = LONG, **extra: object):  # type: ignore[no-untyped-def]
    return call("convert_media", box, {"input": src, "output": dst, **extra}, limits)


def test_wav_to_mp3(media_box: Sandbox) -> None:
    out = convert(media_box, "tone.wav", "tone.mp3")
    assert (out.path, out.format) == ("tone.mp3", "mp3")
    info = describe(media_box, "tone.mp3")
    assert info.audio_streams()[0].codec == "mp3"
    assert info.duration_s == pytest.approx(2.0, abs=0.2)


def test_video_to_webm_keeps_both_streams(media_box: Sandbox) -> None:
    convert(media_box, "clip.mp4", "clip.webm")
    info = describe(media_box, "clip.webm")
    assert info.video_streams()[0].codec == "vp9"
    assert info.audio_streams()[0].codec == "opus"


def test_video_to_audio_format_drops_the_video(media_box: Sandbox) -> None:
    convert(media_box, "clip.mp4", "clip.ogg")
    info = describe(media_box, "clip.ogg")
    assert info.video_streams() == []
    assert info.audio_streams()[0].codec == "vorbis"


def test_video_to_gif_has_no_audio(media_box: Sandbox) -> None:
    convert(media_box, "clip.mp4", "clip.gif")
    info = describe(media_box, "clip.gif")
    assert info.video_streams()[0].codec == "gif"
    assert info.audio_streams() == []


def test_audio_quality_options_are_applied(media_box: Sandbox) -> None:
    low = convert(media_box, "tone.wav", "low.mp3", audio_bitrate_kbps=32)
    high = convert(media_box, "tone.wav", "high.mp3", audio_bitrate_kbps=256)
    assert low.size_bytes < high.size_bytes
    convert(media_box, "tone.wav", "mono16.wav", sample_rate=16000, channels=1)
    stream = describe(media_box, "mono16.wav").audio_streams()[0]
    assert (stream.sample_rate, stream.channels) == (16000, 1)


def test_crf_changes_the_video_size(media_box: Sandbox) -> None:
    good = convert(media_box, "clip.mp4", "good.mp4", crf=10)
    poor = convert(media_box, "clip.mp4", "poor.mp4", crf=45)
    assert poor.size_bytes < good.size_bytes


def test_audio_only_input_cannot_become_video(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        convert(media_box, "tone.wav", "tone.mp4")
    assert not (media_box.root / "tone.mp4").exists()


def test_silent_video_cannot_become_audio(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput):
        convert(media_box, "silent.mp4", "silent.mp3")


@pytest.mark.parametrize("name", ["out.xyz", "out", "out.png", "out.exe"])
def test_unknown_output_formats_are_rejected(media_box: Sandbox, name: str) -> None:
    with pytest.raises(InvalidInput) as info:
        convert(media_box, "tone.wav", name)
    assert "mp3" in info.value.hint


@pytest.mark.parametrize("name", ["corrupt.mp4", "garbage.wav", "evil.m3u8"])
def test_corrupt_input_leaves_no_output(media_box: Sandbox, name: str) -> None:
    with pytest.raises(ToolError) as info:
        convert(media_box, name, "out.mp3")
    assert info.value.code is ErrorCode.CORRUPT
    assert not (media_box.root / "out.mp3").exists()
    assert no_leftovers(media_box)


def test_oversized_input_is_rejected(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        convert(media_box, "clip.mp4", "out.mp3", Limits(timeout_s=60.0, max_media_bytes=100))


def test_oversized_output_is_rejected_and_removed(media_box: Sandbox) -> None:
    limits = Limits(timeout_s=60.0, max_media_bytes=20_000)
    with pytest.raises(LimitExceeded):
        convert(media_box, "tone.wav", "big.wav", limits, sample_rate=48000, channels=2)
    assert not (media_box.root / "big.wav").exists()
    assert no_leftovers(media_box)


def test_read_only_sandbox_refuses(media_box: Sandbox) -> None:
    with pytest.raises(ToolError) as info:
        convert(Sandbox(media_box.root), "tone.wav", "out.mp3")
    assert info.value.code is ErrorCode.WRITE_DISABLED


def test_existing_output_needs_overwrite(media_box: Sandbox) -> None:
    convert(media_box, "tone.wav", "out.mp3")
    first = (media_box.root / "out.mp3").read_bytes()
    with pytest.raises(AlreadyExists):
        convert(media_box, "clip.mp4", "out.mp3")
    assert (media_box.root / "out.mp3").read_bytes() == first
    convert(media_box, "clip.mp4", "out.mp3", overwrite=True)
    assert (media_box.root / "out.mp3").read_bytes() != first


def test_create_parents(media_box: Sandbox) -> None:
    with pytest.raises(NotFound):
        convert(media_box, "tone.wav", "new/out.mp3")
    convert(media_box, "tone.wav", "new/out.mp3", create_parents=True)
    assert (media_box.root / "new" / "out.mp3").exists()


@pytest.mark.parametrize("path", ["../x.wav", "/etc/passwd", "a/../../x.wav"])
def test_input_escape_attempts_are_rejected(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        convert(media_box, path, "out.mp3")


@pytest.mark.parametrize("path", ["../out.mp3", "/tmp/out.mp3", "a/../../out.mp3"])
def test_output_escape_attempts_are_rejected(media_box: Sandbox, path: str) -> None:
    with pytest.raises(SandboxViolation):
        convert(media_box, "tone.wav", path, create_parents=True)


def test_dash_leading_names_are_not_taken_as_options(media_box: Sandbox) -> None:
    (media_box.root / "-i.wav").write_bytes((media_box.root / "tone.wav").read_bytes())
    convert(media_box, "-i.wav", "-y.mp3")
    assert (media_box.root / "-y.mp3").exists()


def test_unknown_and_out_of_range_arguments_are_rejected(media_box: Sandbox) -> None:
    for extra in ({"codec": "libx264"}, {"crf": 99}, {"audio_bitrate_kbps": 0}, {"channels": 5}):
        with pytest.raises(InvalidInput):
            convert(media_box, "tone.wav", "o.mp3", **extra)


def test_encoder_rejecting_the_settings_is_an_invalid_input(media_box: Sandbox) -> None:
    with pytest.raises(InvalidInput) as info:
        convert(media_box, "tone.wav", "out.ogg", audio_bitrate_kbps=256)
    assert "audio_bitrate_kbps" in info.value.hint
    assert no_leftovers(media_box)


def test_default_ogg_works_for_low_sample_rate_sources(media_box: Sandbox) -> None:
    convert(media_box, "tone.wav", "out.ogg")
    assert describe(media_box, "out.ogg").audio_streams()[0].codec == "vorbis"
