"""Resource limits shared by all tools."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from toolbelt.core.errors import InvalidInput, LimitExceeded, ToolTimeout


@dataclass(frozen=True)
class Limits:
    """Defaults are conservative on purpose. Callers raise them explicitly."""

    max_read_bytes: int = 1_000_000
    max_entries: int = 1_000
    timeout_s: float = 10.0

    def with_overrides(self, **overrides: Any) -> Limits:
        unknown = set(overrides) - set(self.__dataclass_fields__)
        if unknown:
            raise InvalidInput(
                f"unknown limit: {', '.join(sorted(unknown))}",
                hint=f"valid limits: {', '.join(self.__dataclass_fields__)}",
            )
        return replace(self, **overrides)


def cap(requested: int | None, limit: int, name: str) -> int:
    """Return the effective value for a per-call knob that may not exceed `limit`."""
    if requested is None:
        return limit
    if requested < 1:
        raise InvalidInput(f"{name} must be at least 1, got {requested}")
    if requested > limit:
        raise LimitExceeded(
            f"{name}={requested} exceeds the allowed maximum of {limit}",
            hint=f"use {name} <= {limit}",
        )
    return requested


class Deadline:
    """Cooperative timeout. Tools call `check()` inside their loops."""

    def __init__(self, timeout_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._timeout_s = timeout_s
        self._expires_at = clock() + timeout_s

    def check(self) -> None:
        if self._clock() > self._expires_at:
            raise ToolTimeout(
                f"tool exceeded its time limit of {self._timeout_s:g}s",
                hint="narrow the request or raise the timeout limit",
            )
