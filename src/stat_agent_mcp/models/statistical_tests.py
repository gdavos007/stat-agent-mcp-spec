"""Public models for approved statistical test requests and results."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stat_agent_mcp.models.common import ExtractionInfo, ToolError

TestValue = str | int | float | bool


class WelchTestInput(BaseModel):
    """Validated input for the MVP Welch independent-samples test."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: Literal["welch_t_test"]
    table: str = Field(min_length=1)
    outcome_column: str = Field(min_length=1)
    grouping_column: str = Field(min_length=1)
    group_values: tuple[TestValue, TestValue]
    alpha: float = Field(gt=0.0, lt=1.0)
    max_rows: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_distinct_columns(self) -> Self:
        """Reject an ambiguous outcome/grouping column overlap."""
        if self.outcome_column == self.grouping_column:
            raise ValueError("outcome and grouping columns must differ")
        return self


class TwoProportionTestInput(BaseModel):
    """Validated input for the MVP two-proportion z-test."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: Literal["two_proportion_z_test"]
    table: str = Field(min_length=1)
    outcome_column: str = Field(min_length=1)
    grouping_column: str = Field(min_length=1)
    group_values: tuple[TestValue, TestValue]
    success_value: TestValue
    alpha: float = Field(gt=0.0, lt=1.0)
    max_rows: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_distinct_columns(self) -> Self:
        """Reject an ambiguous outcome/grouping column overlap."""
        if self.outcome_column == self.grouping_column:
            raise ValueError("outcome and grouping columns must differ")
        return self


class NumericGroupSummary(BaseModel):
    """Auditable summary of one independent numeric sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    group_value: TestValue
    sample_size: int
    mean: float
    standard_deviation: float


class WelchTestResult(BaseModel):
    """Complete successful result for Welch's independent two-sample t-test."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: Literal["welch_t_test"] = "welch_t_test"
    test_name: Literal["Welch's independent two-sample t-test"] = (
        "Welch's independent two-sample t-test"
    )
    null_hypothesis: str
    alternative_hypothesis: str
    alpha: float
    statistic: float
    p_value: float
    significant: bool
    group_summaries: tuple[NumericGroupSummary, NumericGroupSummary]
    effect_size_name: Literal["hedges_g"] = "hedges_g"
    effect_size: float
    effect_size_direction: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    rows_examined: int
    rows_included: int
    null_rows_excluded: int
    invalid_rows_excluded: int
    unselected_group_rows_excluded: int
    extraction: ExtractionInfo


class ProportionGroupSummary(BaseModel):
    """Auditable success summary for one independent group."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    group_value: TestValue
    successes: int
    sample_size: int
    proportion: float


class TwoProportionTestResult(BaseModel):
    """Complete successful result for the two-proportion z-test."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    test_id: Literal["two_proportion_z_test"] = "two_proportion_z_test"
    test_name: Literal["Two-proportion z-test"] = "Two-proportion z-test"
    null_hypothesis: str
    alternative_hypothesis: str
    success_value: TestValue
    alpha: float
    statistic: float
    p_value: float
    significant: bool
    group_summaries: tuple[ProportionGroupSummary, ProportionGroupSummary]
    effect_size_name: Literal["risk_difference"] = "risk_difference"
    effect_size: float
    effect_size_direction: str
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    rows_examined: int
    rows_included: int
    null_rows_excluded: int
    invalid_rows_excluded: int
    unselected_group_rows_excluded: int
    extraction: ExtractionInfo


StatisticalTestResult = Annotated[
    WelchTestResult | TwoProportionTestResult,
    Field(discriminator="test_id"),
]


class RunTestSuccess(BaseModel):
    """Successful run_test envelope designed for future result variants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["success"] = "success"
    result: StatisticalTestResult


RunTestResponse = Annotated[RunTestSuccess | ToolError, Field(discriminator="status")]
