"""A small registry used to test adapters independently of the real tools."""

from typing import Literal

from pydantic import Field

from toolbelt.core.context import Context
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import Registry


class EchoInput(ToolInput):
    text: str = Field(description="Text to repeat.")
    repeat: int = Field(default=1, ge=1, le=5, description="How many times to repeat it.")
    case: Literal["keep", "upper"] = "keep"
    suffix: str | None = None


class Line(ToolOutput):
    index: int
    text: str


class EchoOutput(ToolOutput):
    lines: list[Line]


class PingInput(ToolInput):
    pass


class PingOutput(ToolOutput):
    ok: bool


def make_sample_registry() -> Registry:
    registry = Registry()

    @registry.tool
    def echo(args: EchoInput, ctx: Context) -> EchoOutput:
        """Repeat a text a few times, optionally upper-cased."""
        text = args.text.upper() if args.case == "upper" else args.text
        return EchoOutput(
            lines=[Line(index=i, text=text + (args.suffix or "")) for i in range(args.repeat)]
        )

    @registry.tool
    def ping(args: PingInput, ctx: Context) -> PingOutput:
        """Check that the tool layer is alive."""
        return PingOutput(ok=True)

    return registry
