"""Public models for bounded deterministic table profiles."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from stat_agent_mcp.models.common import ExtractionInfo, ToolError

ProfileValue = str | int | float | bool


class SuggestedRole(StrEnum):
    """Rule-based statistical role suggested for a profiled column."""

    CONTINUOUS_OUTCOME = "continuous_outcome"
    BINARY_OUTCOME = "binary_outcome"
    GROUPING_VARIABLE = "grouping_variable"
    IDENTIFIER = "identifier"
    DATETIME = "datetime"
    OTHER = "other"


class NumericSummary(BaseModel):
    """Finite numeric summaries for a column when applicable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum: float
    maximum: float
    mean: float
    median: float
    standard_deviation: float | None


class ValueFrequency(BaseModel):
    """One safely serialized categorical value and its bounded count."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: ProfileValue
    count: int


class ColumnProfile(BaseModel):
    """Deterministic bounded profile of one database column."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    database_type: str
    pandas_type: str
    suggested_role: SuggestedRole
    row_count_considered: int
    non_null_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    example_values: tuple[ProfileValue, ...]
    numeric_summary: NumericSummary | None
    top_values: tuple[ValueFrequency, ...]


class ProfileTableInput(BaseModel):
    """Validated input for profile_table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table: str = Field(min_length=1)
    max_rows: int | None = Field(default=None, gt=0)


class TableProfileData(BaseModel):
    """Database-independent profile produced by the profiling service."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table_name: str
    row_count_considered: int
    columns: tuple[ColumnProfile, ...]
    extraction: ExtractionInfo


class ProfileTableSuccess(TableProfileData):
    """Successful profile_table response."""

    status: Literal["success"] = "success"
    connection_name: str


ProfileTableResponse = Annotated[ProfileTableSuccess | ToolError, Field(discriminator="status")]
