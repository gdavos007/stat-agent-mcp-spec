"""MCP boundary adapter for approved statistical tests."""

import logging
from typing import Annotated, Literal, cast

from mcp.server.fastmcp import FastMCP
from pydantic import Field, ValidationError

from stat_agent_mcp.errors import InvalidSuccessValueError, StatAgentError, UnsupportedTestError
from stat_agent_mcp.models.common import ToolError
from stat_agent_mcp.models.statistical_tests import (
    RunTestResponse,
    RunTestSuccess,
    TestValue,
    TwoProportionTestInput,
    TwoProportionTestResult,
    WelchTestInput,
    WelchTestResult,
)
from stat_agent_mcp.services.testing import TestingService

_LOGGER = logging.getLogger(__name__)

_DESCRIPTION = """Run one approved statistical test on a deterministic bounded table extract.

Use Welch `welch_t_test` for a two-sided independent-samples comparison of numeric means without an
equal-variance assumption. Use the two-proportion `two_proportion_z_test` for a comparison of
binary success proportions, and always provide the explicit success value; the server never guesses
it. Both tests require a conservative table identifier, outcome and grouping columns, exactly two
group values, alpha between 0 and 1, and an optional row cap. The configured hard row limit always
applies; truncation and first-N bias are reported. Rows with null outcomes or groups are excluded
and counted. Welch rejects non-numeric or non-finite outcomes and needs two observations per group.
The proportion test requires an exactly binary selected outcome and at least five successes and five
failures per group. Do not use either test for paired/repeated observations or causal conclusions.
Results contain maintained-library statistics and p-values, effect sizes, assumptions, warnings,
and audit metadata. Significance does not establish causality or business importance.
"""


def register_run_test(server: FastMCP, testing_service: TestingService) -> None:
    """Register run_test with its database-independent testing service."""

    @server.tool(name="run_test", description=_DESCRIPTION, structured_output=True)
    def run_test(
        test_id: Annotated[
            str,
            Field(description="welch_t_test or two_proportion_z_test"),
        ],
        table: Annotated[str, Field(description="Conservative table identifier")],
        outcome_column: Annotated[str, Field(description="Numeric continuous outcome column")],
        grouping_column: Annotated[str, Field(description="Column containing independent groups")],
        group_values: Annotated[list[TestValue], Field(description="Exactly two group values")],
        alpha: Annotated[
            float,
            Field(description="Significance threshold strictly between 0 and 1"),
        ],
        success_value: Annotated[
            TestValue | None,
            Field(description="Required explicit success value for two_proportion_z_test"),
        ] = None,
        max_rows: Annotated[
            int | None,
            Field(description="Optional requested row cap; the server hard limit always applies"),
        ] = None,
    ) -> RunTestResponse:
        if test_id not in {"welch_t_test", "two_proportion_z_test"}:
            error = UnsupportedTestError()
            return ToolError(code=error.code, message=str(error), retryable=error.retryable)
        try:
            normalized_groups = cast(tuple[TestValue, TestValue], tuple(group_values))
            result: WelchTestResult | TwoProportionTestResult
            if test_id == "welch_t_test":
                request = WelchTestInput(
                    test_id=cast(Literal["welch_t_test"], test_id),
                    table=table,
                    outcome_column=outcome_column,
                    grouping_column=grouping_column,
                    group_values=normalized_groups,
                    alpha=alpha,
                    max_rows=max_rows,
                )
                result = testing_service.run_welch(request)
            else:
                if success_value is None:
                    raise InvalidSuccessValueError
                proportion_request = TwoProportionTestInput(
                    test_id=cast(Literal["two_proportion_z_test"], test_id),
                    table=table,
                    outcome_column=outcome_column,
                    grouping_column=grouping_column,
                    group_values=normalized_groups,
                    success_value=success_value,
                    alpha=alpha,
                    max_rows=max_rows,
                )
                result = testing_service.run_two_proportion(proportion_request)
        except ValidationError:
            return ToolError(
                code="invalid_request",
                message="The statistical test request is invalid.",
                retryable=False,
            )
        except StatAgentError as error:
            return ToolError(
                code=error.code,
                message=str(error),
                retryable=error.retryable,
            )
        except Exception as error:
            _LOGGER.error("Unexpected run_test failure (%s)", type(error).__name__)
            return ToolError(
                code="internal_error",
                message="An unexpected internal error occurred.",
                retryable=False,
            )
        return RunTestSuccess(result=result)
