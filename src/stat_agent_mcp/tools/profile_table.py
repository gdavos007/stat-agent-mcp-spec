"""MCP boundary adapter for deterministic bounded table profiling."""

import logging
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field, ValidationError

from stat_agent_mcp.errors import StatAgentError
from stat_agent_mcp.models.common import ToolError
from stat_agent_mcp.models.profiles import (
    ProfileTableInput,
    ProfileTableResponse,
    ProfileTableSuccess,
)
from stat_agent_mcp.services.profiling import ProfilingService

_LOGGER = logging.getLogger(__name__)

_DESCRIPTION = """Profile one table using deterministic, rule-based heuristics.

Provide a conservative table identifier and an optional positive maximum row count. The server
selects only that table's columns, orders rows deterministically, and clamps extraction to the
configured hard limit. It reports whether first-N limiting truncated the table. SQL and sampling
cannot be provided. Nulls remain excluded from summaries and are counted for every column. Suggested
roles are advisory and use database/pandas type, primary-key metadata, cardinality, uniqueness,
and null counts; no LLM is called. Examples are capped and suppressed for identifier or
secret-like columns, but this tool is not a comprehensive PII detector.
"""


def register_profile_table(
    server: FastMCP,
    profiling_service: ProfilingService,
    connection_name: str,
) -> None:
    """Register profile_table with its database-independent profiling service."""

    @server.tool(
        name="profile_table",
        description=_DESCRIPTION,
        structured_output=True,
    )
    def profile_table(
        table: Annotated[str, Field(description="Conservative table identifier")],
        max_rows: Annotated[
            int | None,
            Field(description="Optional requested row cap; the server hard limit always applies"),
        ] = None,
    ) -> ProfileTableResponse:
        try:
            request = ProfileTableInput(table=table, max_rows=max_rows)
            profile = profiling_service.profile(request.table, request.max_rows)
        except ValidationError:
            return ToolError(
                code="invalid_request",
                message="The profile request is invalid.",
                retryable=False,
            )
        except StatAgentError as error:
            return ToolError(
                code=error.code,
                message=str(error),
                retryable=error.retryable,
            )
        except Exception as error:
            _LOGGER.error("Unexpected profile_table failure (%s)", type(error).__name__)
            return ToolError(
                code="internal_error",
                message="An unexpected internal error occurred.",
                retryable=False,
            )

        return ProfileTableSuccess(
            connection_name=connection_name,
            **profile.model_dump(),
        )
