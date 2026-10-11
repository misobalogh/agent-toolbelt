from pathlib import Path

import pytest

from toolbelt.core.errors import ErrorCode, InvalidInput, SandboxViolation
from toolbelt.core.sandbox import Sandbox


@pytest.fixture
def root(tmp_path: Path) -> Path:
    base = tmp_path / "root"
    base.mkdir()
    (base / "docs").mkdir()
    (base / "docs" / "a.txt").write_text("hello")
    return base


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    base = tmp_path / "elsewhere"
    base.mkdir()
    (base / "secret.txt").write_text("secret")
    return base


def test_root_must_be_a_directory(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput):
        Sandbox(tmp_path / "missing")


def test_relative_path_resolves_inside_root(root: Path) -> None:
    assert Sandbox(root).resolve("docs/a.txt") == root / "docs" / "a.txt"


def test_empty_and_dot_resolve_to_root(root: Path) -> None:
    box = Sandbox(root)
    assert box.resolve("") == root
    assert box.resolve(".") == root


def test_missing_path_inside_root_resolves(root: Path) -> None:
    assert Sandbox(root).resolve("new/file.txt") == root / "new" / "file.txt"


def test_dotdot_that_stays_inside_is_allowed(root: Path) -> None:
    assert Sandbox(root).resolve("docs/../docs/a.txt") == root / "docs" / "a.txt"


def test_dotdot_traversal_is_rejected(root: Path) -> None:
    with pytest.raises(SandboxViolation) as info:
        Sandbox(root).resolve("../elsewhere/secret.txt")
    assert info.value.code is ErrorCode.OUTSIDE_SANDBOX


def test_deep_dotdot_traversal_is_rejected(root: Path) -> None:
    with pytest.raises(SandboxViolation):
        Sandbox(root).resolve("docs/../../../../../etc/passwd")


def test_absolute_path_outside_is_rejected(root: Path, outside: Path) -> None:
    with pytest.raises(SandboxViolation):
        Sandbox(root).resolve(str(outside / "secret.txt"))


def test_absolute_path_inside_is_allowed(root: Path) -> None:
    target = root / "docs" / "a.txt"
    assert Sandbox(root).resolve(str(target)) == target


def test_symlink_to_outside_file_is_rejected(root: Path, outside: Path) -> None:
    (root / "link.txt").symlink_to(outside / "secret.txt")
    with pytest.raises(SandboxViolation):
        Sandbox(root).resolve("link.txt")


def test_symlink_to_outside_dir_is_rejected(root: Path, outside: Path) -> None:
    (root / "linkdir").symlink_to(outside, target_is_directory=True)
    with pytest.raises(SandboxViolation):
        Sandbox(root).resolve("linkdir/secret.txt")


def test_symlink_pointing_inside_is_allowed(root: Path) -> None:
    (root / "alias.txt").symlink_to(root / "docs" / "a.txt")
    assert Sandbox(root).resolve("alias.txt") == root / "docs" / "a.txt"


def test_display_is_root_relative_posix(root: Path) -> None:
    box = Sandbox(root)
    assert box.display(box.resolve("docs/a.txt")) == "docs/a.txt"
    assert box.display(box.resolve(".")) == "."
