"""Small helpers shared by the media tool tests."""

from toolbelt.core.limits import Limits
from toolbelt.core.media import MediaProbe
from toolbelt.core.registry import default_registry
from toolbelt.core.sandbox import Sandbox
from toolbelt.tools.media_common import MediaResult

LONG = Limits(timeout_s=60.0)


def call(tool: str, box: Sandbox, args: dict[str, object], limits: Limits = LONG) -> MediaResult:
    result = default_registry.call(tool, args, box, limits)
    assert isinstance(result, MediaResult)
    return result


def describe(box: Sandbox, path: str) -> MediaProbe:
    result = default_registry.call("media_info", {"path": path}, box, LONG)
    assert isinstance(result, MediaProbe)
    return result


def no_leftovers(box: Sandbox) -> bool:
    return not [p for p in box.root.rglob(".toolbelt-*")]
