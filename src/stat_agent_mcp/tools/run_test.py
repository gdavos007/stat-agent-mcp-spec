"""MCP boundary adapter for approved statistical tests."""

import logging
from typing import Annotated, Literal, cast

from mcp.server.fastmcp import FastMCP
from pydantic import Field, ValidationError

from stat_agent_mcp.errors import StatAgentError, UnsupportedTestError
from stat_agent_mcp.models.common import ToolError
from stat_agent_mcp.models.statistical_tests import (
    RunTestResponse,
    RunTestSuccess,
    TestValue,
    WelchTestInput,
)
from stat_agent_mcp.services.testing import TestingService

_LOGGER = logging.getLogger(__name__)

_DESCRIPTION = """Run an approved statistical test on a deterministic bounded table extract.

Milestone 4 supports only the Welch `welch_t_test`, a two-sided independent-samples comparison that
does not assume equal variance. Provide a conservative table identifier, numeric outcome column,
grouping column, exactly two explicit group values, alpha between 0 and 1, and an optional positive
row cap. The configured hard row limit always applies; truncation and first-N bias are reported.
Rows with null outcomes or groups are excluded and counted. Non-null non-numeric or non-finite
outcomes are rejected rather than silently discarded. Each group needs at least two observations.
Do not use this test for paired/repeated observations, categorical outcomes, or causal conclusions.
The result contains SciPy's statistic and p-value, Hedges' g from statsmodels, assumptions,
warnings, and audit metadata. Significance does not establish causality or business importance.
`two_proportion_z_test` remains unsupported until its dedicated milestone.
"""


def register_run_test(server: FastMCP, testing_service: TestingService) -> None:
    """Register run_test with its database-independent testing service."""

    @server.tool(name="run_test", description=_DESCRIPTION, structured_output=True)
    def run_test(
        test_id: Annotated[str, Field(description="Supported value: welch_t_test")],
        table: Annotated[str, Field(description="Conservative table identifier")],
        outcome_column: Annotated[str, Field(description="Numeric continuous outcome column")],
        grouping_column: Annotated[str, Field(description="Column containing independent groups")],
        group_values: Annotated[list[TestValue], Field(description="Exactly two group values")],
        alpha: Annotated[
            float,
            Field(description="Significance threshold strictly between 0 and 1"),
        ],
        max_rows: Annotated[
            int | None,
            Field(description="Optional requested row cap; the server hard limit always applies"),
        ] = None,
    ) -> RunTestResponse:
        if test_id != "welch_t_test":
            error = UnsupportedTestError()
            return ToolError(code=error.code, message=str(error), retryable=error.retryable)
        try:
            request = WelchTestInput(
                test_id=cast(Literal["welch_t_test"], test_id),
                table=table,
                outcome_column=outcome_column,
                grouping_column=grouping_column,
                group_values=cast(tuple[TestValue, TestValue], tuple(group_values)),
                alpha=alpha,
                max_rows=max_rows,
            )
            result = testing_service.run_welch(request)
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
