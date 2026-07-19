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


class ExtractionInfo(BaseModel):
    """Public audit metadata for a bounded extraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_limit: int
    effective_limit: int
    hard_limit: int
    rows_examined: int
    truncated: bool
    sampled: bool
    sampling_method: Literal["none"]
    random_seed: None
    order_columns: tuple[str, ...]
