"""MCP boundary adapter for safe table discovery."""

import logging

from mcp.server.fastmcp import FastMCP

from stat_agent_mcp.connectors.base import TableDiscoveryConnector
from stat_agent_mcp.errors import StatAgentError
from stat_agent_mcp.models.common import ToolError
from stat_agent_mcp.models.tables import ListTablesResponse, ListTablesSuccess, TableInfo

_LOGGER = logging.getLogger(__name__)

_DESCRIPTION = """List the tables and views available through the configured SQLite database.

Use this read-only tool to discover relation names before profiling or testing. It accepts no
arguments and never returns the database path or connection credentials. It does not extract data,
so row-limit and null-handling behavior do not apply. It cannot list columns or execute SQL.
"""


def register_list_tables(
    server: FastMCP,
    connector: TableDiscoveryConnector,
    connection_name: str,
) -> None:
    """Register the list_tables tool with its connector dependencies."""

    @server.tool(
        name="list_tables",
        description=_DESCRIPTION,
        structured_output=True,
    )
    def list_tables() -> ListTablesResponse:
        try:
            tables = connector.list_tables()
        except StatAgentError as error:
            return ToolError(
                code=error.code,
                message=str(error),
                retryable=error.retryable,
            )
        except Exception as error:
            _LOGGER.error("Unexpected list_tables failure (%s)", type(error).__name__)
            return ToolError(
                code="internal_error",
                message="An unexpected internal error occurred.",
                retryable=False,
            )

        return ListTablesSuccess(
            connection_name=connection_name,
            tables=tuple(
                TableInfo(name=table.name, table_type=table.table_type) for table in tables
            ),
        )
