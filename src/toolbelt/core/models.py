"""Base classes for tool models."""

from pydantic import BaseModel, ConfigDict


class ToolInput(BaseModel):
    """Unknown fields are rejected so that an agent's typo becomes a visible error."""

    model_config = ConfigDict(extra="forbid")


class ToolOutput(BaseModel):
    pass
