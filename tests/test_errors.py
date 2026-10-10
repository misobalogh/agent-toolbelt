from toolbelt.core.errors import ErrorCode, LimitExceeded, NotFound, SandboxViolation, ToolError


def test_to_dict_has_code_message_and_hint() -> None:
    err = NotFound("no such file: a.txt", hint="call list_dir first")
    assert err.to_dict() == {
        "code": "not_found",
        "message": "no such file: a.txt",
        "hint": "call list_dir first",
    }


def test_subclasses_carry_their_default_code() -> None:
    assert SandboxViolation("x").code is ErrorCode.OUTSIDE_SANDBOX
    assert LimitExceeded("x").code is ErrorCode.LIMIT_EXCEEDED


def test_explicit_code_overrides_default() -> None:
    err = ToolError("x", code=ErrorCode.CORRUPT)
    assert err.code is ErrorCode.CORRUPT


def test_str_is_the_message() -> None:
    assert str(NotFound("gone")) == "gone"
