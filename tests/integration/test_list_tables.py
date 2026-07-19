"""Integration tests for the list_tables MCP contract."""

import asyncio
import logging
from pathlib import Path

from _pytest.logging import LogCaptureFixture
from mcp.server.fastmcp import FastMCP
from pydantic import SecretStr

from stat_agent_mcp.config import Settings
from stat_agent_mcp.connectors.base import TableMetadata
from stat_agent_mcp.server import create_server
from stat_agent_mcp.tools.list_tables import register_list_tables


def settings_for(database_path: Path) -> Settings:
    """Build test settings without loading process environment variables."""
    return Settings(
        connection_name="demo_sqlite",
        sqlite_path_secret=SecretStr(str(database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )


def test_server_registers_list_tables_with_structured_contract(demo_database_path: Path) -> None:
    server = create_server(settings_for(demo_database_path))

    tools = asyncio.run(server.list_tools())

    list_tables_tool = next(tool for tool in tools if tool.name == "list_tables")
    assert list_tables_tool.inputSchema["properties"] == {}
    assert list_tables_tool.outputSchema is not None
    assert "row-limit and null-handling behavior do not apply" in (
        list_tables_tool.description or ""
    )


def test_list_tables_returns_structured_safe_metadata(demo_database_path: Path) -> None:
    server = create_server(settings_for(demo_database_path))

    result = asyncio.run(server.call_tool("list_tables", {}))
    assert isinstance(result, tuple)
    content, structured = result

    assert structured["result"] == {
        "status": "success",
        "connection_name": "demo_sqlite",
        "database_engine": "sqlite",
        "tables": [{"name": "experiment_results", "table_type": "table"}],
    }
    assert str(demo_database_path) not in repr(content)
    assert str(demo_database_path) not in repr(structured)


def test_list_tables_returns_structured_error_without_crashing(tmp_path: Path) -> None:
    missing_path = tmp_path / "private-client.sqlite3"
    server = create_server(settings_for(missing_path))

    result = asyncio.run(server.call_tool("list_tables", {}))
    assert isinstance(result, tuple)
    content, structured = result

    assert structured["result"] == {
        "status": "error",
        "code": "connection_failure",
        "message": "Unable to access the configured database.",
        "retryable": True,
    }
    assert str(missing_path) not in repr(content)
    assert str(missing_path) not in repr(structured)
    assert not missing_path.exists()


def test_list_tables_redacts_unexpected_error_details(caplog: LogCaptureFixture) -> None:
    sensitive_detail = "/private/customer/database.sqlite3"

    class ExplodingConnector:
        def list_tables(self) -> tuple[TableMetadata, ...]:
            raise RuntimeError(sensitive_detail)

    server = FastMCP(name="test")
    register_list_tables(server, ExplodingConnector(), "demo_sqlite")

    with caplog.at_level(logging.ERROR):
        result = asyncio.run(server.call_tool("list_tables", {}))

    assert isinstance(result, tuple)
    content, structured = result
    assert structured["result"] == {
        "status": "error",
        "code": "internal_error",
        "message": "An unexpected internal error occurred.",
        "retryable": False,
    }
    assert sensitive_detail not in repr(content)
    assert sensitive_detail not in repr(structured)
    assert sensitive_detail not in caplog.text
