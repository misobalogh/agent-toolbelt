from pathlib import Path

import pytest
from pydantic import BaseModel

from toolbelt.core.context import Context
from toolbelt.core.errors import ErrorCode, InvalidInput, NotFound, ToolError, UnknownTool
from toolbelt.core.models import ToolInput, ToolOutput
from toolbelt.core.registry import Registry, default_registry
from toolbelt.core.sandbox import Sandbox


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    text: str


def make_echo(registry: Registry) -> None:
    @registry.tool
    def echo(args: EchoInput, ctx: Context) -> EchoOutput:
        """Return the text unchanged."""
        return EchoOutput(text=args.text)


def test_decorator_registers_models_and_description() -> None:
    registry = Registry()
    make_echo(registry)
    spec = registry.get("echo")
    assert spec.input_model is EchoInput
    assert spec.output_model is EchoOutput
    assert spec.description == "Return the text unchanged."


def test_decorator_returns_the_original_function() -> None:
    registry = Registry()

    @registry.tool
    def echo(args: EchoInput, ctx: Context) -> EchoOutput:
        """Return the text unchanged."""
        return EchoOutput(text=args.text)

    assert echo.__name__ == "echo"


def test_specs_are_sorted_by_name() -> None:
    registry = Registry()

    @registry.tool
    def zeta(args: EchoInput, ctx: Context) -> EchoOutput:
        """Last."""
        return EchoOutput(text=args.text)

    @registry.tool
    def alpha(args: EchoInput, ctx: Context) -> EchoOutput:
        """First."""
        return EchoOutput(text=args.text)

    assert [s.name for s in registry.specs()] == ["alpha", "zeta"]


def test_duplicate_names_are_rejected() -> None:
    registry = Registry()
    make_echo(registry)
    with pytest.raises(ValueError, match="already registered"):
        make_echo(registry)


def test_missing_docstring_is_rejected() -> None:
    registry = Registry()
    with pytest.raises(TypeError, match="docstring"):

        @registry.tool
        def silent(args: EchoInput, ctx: Context) -> EchoOutput:
            return EchoOutput(text=args.text)


def test_wrong_signature_is_rejected() -> None:
    registry = Registry()
    with pytest.raises(TypeError, match="signature"):

        @registry.tool  # type: ignore[type-var]
        def broken(args: EchoInput) -> EchoOutput:
            """Missing context."""
            return EchoOutput(text=args.text)


def test_non_model_types_are_rejected() -> None:
    registry = Registry()
    with pytest.raises(TypeError, match="pydantic"):

        @registry.tool  # type: ignore[type-var]
        def plain(args: str, ctx: Context) -> str:
            """Not models."""
            return args


def test_default_registry_is_a_registry() -> None:
    assert isinstance(default_registry, Registry)


class StrictInput(ToolInput):
    count: int


class CountOutput(ToolOutput):
    doubled: int


def make_registry() -> Registry:
    registry = Registry()

    @registry.tool
    def double(args: StrictInput, ctx: Context) -> CountOutput:
        """Double the count."""
        return CountOutput(doubled=args.count * 2)

    @registry.tool
    def explode(args: StrictInput, ctx: Context) -> CountOutput:
        """Always fails with a bare exception."""
        raise RuntimeError("boom")

    @registry.tool
    def refuse(args: StrictInput, ctx: Context) -> CountOutput:
        """Always fails with a typed error."""
        raise NotFound("nothing here", hint="try elsewhere")

    return registry


def test_call_validates_and_runs(tmp_path: Path) -> None:
    result = make_registry().call("double", {"count": 4}, Sandbox(tmp_path))
    assert result == CountOutput(doubled=8)


def test_call_reports_invalid_input_with_field_names(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput) as info:
        make_registry().call("double", {"count": "many"}, Sandbox(tmp_path))
    assert "count" in info.value.message


def test_call_rejects_unknown_fields(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput):
        make_registry().call("double", {"count": 1, "cnt": 2}, Sandbox(tmp_path))


def test_call_unknown_tool_suggests_close_names(tmp_path: Path) -> None:
    with pytest.raises(UnknownTool) as info:
        make_registry().call("doubel", {"count": 1}, Sandbox(tmp_path))
    assert "double" in info.value.hint


def test_call_passes_typed_errors_through(tmp_path: Path) -> None:
    with pytest.raises(NotFound) as info:
        make_registry().call("refuse", {"count": 1}, Sandbox(tmp_path))
    assert info.value.hint == "try elsewhere"


def test_call_wraps_unexpected_exceptions(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as info:
        make_registry().call("explode", {"count": 1}, Sandbox(tmp_path))
    assert info.value.code is ErrorCode.INTERNAL
    assert isinstance(info.value.__cause__, RuntimeError)
