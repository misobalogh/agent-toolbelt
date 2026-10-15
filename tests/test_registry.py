import pytest
from pydantic import BaseModel

from toolbelt.core.context import Context
from toolbelt.core.registry import Registry, default_registry


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
