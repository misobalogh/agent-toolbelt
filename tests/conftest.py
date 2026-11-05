import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from toolbelt.core.sandbox import Sandbox

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


@pytest.fixture
def assert_snapshot() -> Callable[[str, Any], None]:
    """Compare data with tests/snapshots/<name>.json.

    Regenerate with `UPDATE_SNAPSHOTS=1 uv run pytest` and review the diff.
    """

    def check(name: str, data: Any) -> None:
        path = SNAPSHOT_DIR / f"{name}.json"
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        if os.environ.get("UPDATE_SNAPSHOTS"):
            path.write_text(text)
        assert path.exists(), f"missing snapshot {path.name}, run with UPDATE_SNAPSHOTS=1"
        assert path.read_text() == text, f"snapshot {path.name} is out of date"

    return check


def _ffmpeg(*args: str) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-y", *args],
        check=True,
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture(scope="session")
def media_files(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Tiny real media files, generated once with ffmpeg. Tests skip without ffmpeg."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg and ffprobe are required")
    root = tmp_path_factory.mktemp("media")
    tone = ["-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=22050"]
    picture = ["-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=2"]
    _ffmpeg(*tone, "-ac", "1", str(root / "tone.wav"))
    _ffmpeg(*picture, *tone, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(root / "clip.mp4"))  # fmt: skip
    _ffmpeg(*picture, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(root / "silent.mp4"))
    (root / "corrupt.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"not really a movie" * 20)
    (root / "garbage.wav").write_bytes(b"this is plain text, not audio\n" * 20)
    (root / "evil.m3u8").write_text("#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\n/etc/hostname\n")
    (root / "evil.txt").write_text("ffconcat version 1.0\nfile /etc/hostname\n")
    return root


@pytest.fixture
def media_box(media_files: Path, tmp_path: Path) -> Sandbox:
    """A writable sandbox that holds a fresh copy of the media files."""
    root = tmp_path / "root"
    shutil.copytree(media_files, root)
    return Sandbox(root, allow_write=True)
