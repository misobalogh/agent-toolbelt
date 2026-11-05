import pytest

from toolbelt.core.errors import InvalidInput
from toolbelt.core.media_formats import (
    AUDIO_ONLY,
    IMAGE_ONLY,
    SPECS_BY_NAME,
    format_for,
)


@pytest.mark.parametrize(
    ("path", "name"),
    [("a.MP3", "mp3"), ("dir/clip.webm", "webm"), ("x.jpeg", "jpg"), ("a.b.c.flac", "flac")],
)
def test_format_is_chosen_by_extension(path: str, name: str) -> None:
    kinds = ("audio", "video", "image")
    assert format_for(path, kinds).name == name  # type: ignore[arg-type]


def test_kind_must_match_the_tool() -> None:
    with pytest.raises(InvalidInput) as info:
        format_for("a.mp4", AUDIO_ONLY)
    assert "mp3" in info.value.hint
    assert "mp4" not in info.value.hint
    with pytest.raises(InvalidInput):
        format_for("a.mp3", IMAGE_ONLY)


@pytest.mark.parametrize("path", ["noext", "a.", ".mp3", "a.sh", "a.mp3.exe"])
def test_unknown_or_missing_extensions_are_rejected(path: str) -> None:
    with pytest.raises(InvalidInput):
        format_for(path, AUDIO_ONLY)


def test_every_format_names_its_codecs() -> None:
    for spec in SPECS_BY_NAME.values():
        assert spec.audio_codec or spec.video_codec
        if spec.kind == "audio":
            assert spec.video_codec is None
        if spec.kind != "audio":
            assert spec.video_codec
