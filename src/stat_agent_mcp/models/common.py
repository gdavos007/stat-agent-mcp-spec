"""Models shared by MCP tool contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ToolError(BaseModel):
    """Structured, non-secret-bearing MCP tool failure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["error"] = "error"
    code: str
    message: str
    retryable: bool

