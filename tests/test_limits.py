import pytest

from toolbelt.core.errors import InvalidInput, LimitExceeded, ToolTimeout
from toolbelt.core.limits import Deadline, Limits, cap


def test_defaults_are_positive() -> None:
    limits = Limits()
    assert limits.max_read_bytes > 0
    assert limits.max_entries > 0
    assert limits.timeout_s > 0


def test_with_overrides_returns_new_instance() -> None:
    base = Limits()
    changed = base.with_overrides(max_read_bytes=10)
    assert changed.max_read_bytes == 10
    assert base.max_read_bytes != 10


def test_with_overrides_rejects_unknown_names() -> None:
    with pytest.raises(InvalidInput) as info:
        Limits().with_overrides(max_bytez=1)
    assert "max_bytez" in info.value.message


def test_cap_defaults_to_limit() -> None:
    assert cap(None, 100, "max_entries") == 100


def test_cap_accepts_smaller_values() -> None:
    assert cap(5, 100, "max_entries") == 5


def test_cap_rejects_values_above_limit() -> None:
    with pytest.raises(LimitExceeded):
        cap(101, 100, "max_entries")


@pytest.mark.parametrize("value", [0, -3])
def test_cap_rejects_non_positive_values(value: int) -> None:
    with pytest.raises(InvalidInput):
        cap(value, 100, "max_entries")


def test_deadline_passes_before_expiry() -> None:
    now = [0.0]
    deadline = Deadline(5.0, clock=lambda: now[0])
    now[0] = 4.9
    deadline.check()


def test_deadline_raises_after_expiry() -> None:
    now = [0.0]
    deadline = Deadline(5.0, clock=lambda: now[0])
    now[0] = 5.1
    with pytest.raises(ToolTimeout):
        deadline.check()


def test_deadline_reports_the_time_left() -> None:
    now = [0.0]
    deadline = Deadline(5.0, clock=lambda: now[0])
    now[0] = 2.0
    assert deadline.remaining() == 3.0


def test_deadline_remaining_raises_after_expiry() -> None:
    now = [0.0]
    deadline = Deadline(5.0, clock=lambda: now[0])
    now[0] = 5.1
    with pytest.raises(ToolTimeout):
        deadline.remaining()
