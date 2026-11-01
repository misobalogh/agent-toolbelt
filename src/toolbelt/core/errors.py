"""Structured errors that an agent can read and recover from."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    UNKNOWN_TOOL = "unknown_tool"
    NOT_FOUND = "not_found"
    NOT_A_FILE = "not_a_file"
    NOT_A_DIRECTORY = "not_a_directory"
    ALREADY_EXISTS = "already_exists"
    PERMISSION_DENIED = "permission_denied"
    OUTSIDE_SANDBOX = "outside_sandbox"
    WRITE_DISABLED = "write_disabled"
    LIMIT_EXCEEDED = "limit_exceeded"
    TIMEOUT = "timeout"
    UNSUPPORTED = "unsupported"
    CORRUPT = "corrupt"
    INTERNAL = "internal"


class ToolError(Exception):
    """Base class for every error a tool is allowed to raise."""

    default_code = ErrorCode.INTERNAL

    def __init__(self, message: str, hint: str = "", code: ErrorCode | None = None) -> None:
        super().__init__(message)
        self.code = code or self.default_code
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "hint": self.hint}


class InvalidInput(ToolError):
    default_code = ErrorCode.INVALID_INPUT


class UnknownTool(ToolError):
    default_code = ErrorCode.UNKNOWN_TOOL


class NotFound(ToolError):
    default_code = ErrorCode.NOT_FOUND


class AlreadyExists(ToolError):
    default_code = ErrorCode.ALREADY_EXISTS


class PermissionDenied(ToolError):
    default_code = ErrorCode.PERMISSION_DENIED


class SandboxViolation(ToolError):
    default_code = ErrorCode.OUTSIDE_SANDBOX


class LimitExceeded(ToolError):
    default_code = ErrorCode.LIMIT_EXCEEDED


class ToolTimeout(ToolError):
    default_code = ErrorCode.TIMEOUT


class Unsupported(ToolError):
    default_code = ErrorCode.UNSUPPORTED
