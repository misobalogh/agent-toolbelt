from pathlib import Path

import pytest

from toolbelt.core.context import Context
from toolbelt.core.errors import (
    AlreadyExists,
    ErrorCode,
    LimitExceeded,
    ToolError,
    ToolTimeout,
)
from toolbelt.core.limits import Deadline, Limits
from toolbelt.core.media import MediaInput, probe, run_ffmpeg
from toolbelt.core.sandbox import Sandbox


def make_ctx(box: Sandbox, **limits: float) -> Context:
    lim = Limits().with_overrides(timeout_s=60.0, **limits)
    return Context(box, lim, Deadline(lim.timeout_s))


def to_mp3(ctx: Context, src: str, dst: str, *, overwrite: bool = False) -> int:
    return run_ffmpeg(
        ctx,
        inputs=[MediaInput(ctx.sandbox.input_path(src))],
        output=ctx.sandbox.output_path(dst, overwrite=overwrite),
        muxer="mp3",
        args=["-vn", "-c:a", "libmp3lame"],
        overwrite=overwrite,
    )


def leftovers(box: Sandbox) -> list[str]:
    return [p.name for p in box.root.iterdir() if p.name.startswith(".toolbelt-")]


def test_probe_describes_an_audio_file(media_box: Sandbox) -> None:
    info = probe(make_ctx(media_box), media_box.input_path("tone.wav"))
    assert info.format_name == "wav"
    assert info.duration_s == pytest.approx(2.0, abs=0.1)
    assert [(s.type, s.codec, s.sample_rate, s.channels) for s in info.streams] == [
        ("audio", "pcm_s16le", 22050, 1)
    ]


def test_probe_describes_video_and_audio_streams(media_box: Sandbox) -> None:
    info = probe(make_ctx(media_box), media_box.input_path("clip.mp4"))
    video = info.video_streams()[0]
    assert (video.codec, video.width, video.height, video.fps) == ("h264", 64, 48, 10.0)
    assert info.audio_streams()[0].codec == "aac"


@pytest.mark.parametrize("name", ["corrupt.mp4", "garbage.wav"])
def test_probe_rejects_corrupt_files(media_box: Sandbox, name: str) -> None:
    with pytest.raises(ToolError) as info:
        probe(make_ctx(media_box), media_box.input_path(name))
    assert info.value.code is ErrorCode.CORRUPT
    assert str(media_box.root) not in info.value.message


@pytest.mark.parametrize("name", ["evil.m3u8", "evil.txt", "disguised.png"])
def test_playlist_like_inputs_are_refused(media_box: Sandbox, name: str) -> None:
    with pytest.raises(ToolError) as info:
        probe(make_ctx(media_box), media_box.input_path(name))
    assert info.value.code is ErrorCode.CORRUPT


def test_ffmpeg_refuses_playlist_inputs_too(media_box: Sandbox) -> None:
    with pytest.raises(ToolError):
        to_mp3(make_ctx(media_box), "evil.m3u8", "out.mp3")
    assert not (media_box.root / "out.mp3").exists()
    assert leftovers(media_box) == []


def test_run_ffmpeg_writes_the_output(media_box: Sandbox) -> None:
    size = to_mp3(make_ctx(media_box), "clip.mp4", "out.mp3")
    assert size == (media_box.root / "out.mp3").stat().st_size > 0
    assert leftovers(media_box) == []


def test_existing_output_is_kept_without_overwrite(media_box: Sandbox) -> None:
    (media_box.root / "out.mp3").write_bytes(b"old")
    ctx = make_ctx(media_box)
    with pytest.raises(AlreadyExists):
        run_ffmpeg(
            ctx,
            inputs=[MediaInput(media_box.input_path("tone.wav"))],
            output=media_box.root / "out.mp3",
            muxer="mp3",
            args=["-c:a", "libmp3lame"],
            overwrite=False,
        )
    assert (media_box.root / "out.mp3").read_bytes() == b"old"
    assert leftovers(media_box) == []


def test_overwrite_replaces_the_output(media_box: Sandbox) -> None:
    (media_box.root / "out.mp3").write_bytes(b"old")
    to_mp3(make_ctx(media_box), "tone.wav", "out.mp3", overwrite=True)
    assert (media_box.root / "out.mp3").read_bytes() != b"old"


def test_failed_run_leaves_no_partial_file(media_box: Sandbox) -> None:
    with pytest.raises(ToolError):
        to_mp3(make_ctx(media_box), "corrupt.mp4", "out.mp3")
    assert not (media_box.root / "out.mp3").exists()
    assert leftovers(media_box) == []


def test_output_over_the_limit_is_rejected_and_removed(media_box: Sandbox) -> None:
    with pytest.raises(LimitExceeded):
        to_mp3(make_ctx(media_box, max_media_bytes=5000), "tone.wav", "out.mp3")
    assert not (media_box.root / "out.mp3").exists()
    assert leftovers(media_box) == []


def test_expired_deadline_raises_a_timeout(media_box: Sandbox) -> None:
    ctx = Context(media_box, Limits(), Deadline(-1.0))
    with pytest.raises(ToolTimeout):
        probe(ctx, media_box.input_path("tone.wav"))


def test_missing_ffmpeg_is_reported(media_box: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(Path("/nonexistent")))
    with pytest.raises(ToolError) as info:
        probe(make_ctx(media_box), media_box.input_path("tone.wav"))
    assert info.value.code is ErrorCode.UNSUPPORTED
