"""Everything a tool may touch, passed in explicitly instead of held globally."""

from __future__ import annotations

from dataclasses import dataclass

from toolbelt.core.limits import Deadline, Limits
from toolbelt.core.sandbox import Sandbox


@dataclass(frozen=True)
class Context:
    sandbox: Sandbox
    limits: Limits
    deadline: Deadline
