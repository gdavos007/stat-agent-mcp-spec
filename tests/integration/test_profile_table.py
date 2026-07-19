"""Integration tests for bounded profile_table behavior."""

import asyncio
from pathlib import Path
from typing import Any, cast

from mcp.server.fastmcp import FastMCP
from pydantic import SecretStr

from stat_agent_mcp.config import Settings
from stat_agent_mcp.server import create_server


def settings_for(database_path: Path) -> Settings:
    """Build profile integration settings without reading process environment variables."""
    return Settings(
        connection_name="demo_sqlite",
        sqlite_path_secret=SecretStr(str(database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )


def structured_result(
    server: FastMCP,
    tool_name: str,
    arguments: dict[str, object],
) -> dict[str, Any]:
    result = asyncio.run(server.call_tool(tool_name, arguments))
    assert isinstance(result, tuple)
    _, structured = result
    return cast(dict[str, Any], structured["result"])


def test_profile_table_returns_deterministic_structured_profile(
    demo_database_path: Path,
) -> None:
    server = create_server(settings_for(demo_database_path))

    profile = structured_result(server, "profile_table", {"table": "experiment_results"})

    assert profile["status"] == "success"
    assert profile["connection_name"] == "demo_sqlite"
    assert profile["table_name"] == "experiment_results"
    assert profile["row_count_considered"] == 40
    assert profile["extraction"]["truncated"] is False
    columns = {item["name"]: item for item in profile["columns"]}
    assert columns["record_id"]["suggested_role"] == "identifier"
    assert columns["record_id"]["example_values"] == []
    assert columns["variant"]["suggested_role"] == "grouping_variable"
    assert columns["account_balance"]["suggested_role"] == "continuous_outcome"
    assert columns["account_balance"]["null_count"] == 2
    assert columns["converted"]["suggested_role"] == "binary_outcome"
    assert columns["converted"]["null_count"] == 2


def test_profile_table_clamps_to_hard_limit_and_reports_truncation(
    demo_database_path: Path,
) -> None:
    settings = settings_for(demo_database_path).model_copy(
        update={"default_row_limit": 5, "hard_row_limit": 10}
    )
    server = create_server(settings)

    profile = structured_result(
        server,
        "profile_table",
        {"table": "experiment_results", "max_rows": 1_000},
    )

    assert profile["row_count_considered"] == 10
    extraction = profile["extraction"]
    assert extraction["requested_limit"] == 1_000
    assert extraction["effective_limit"] == 10
    assert extraction["hard_limit"] == 10
    assert extraction["truncated"] is True


def test_profile_table_rejects_unsafe_and_missing_tables(demo_database_path: Path) -> None:
    server = create_server(settings_for(demo_database_path))

    unsafe = structured_result(server, "profile_table", {"table": "users; DROP TABLE users"})
    missing = structured_result(server, "profile_table", {"table": "missing_table"})

    assert unsafe["status"] == "error"
    assert unsafe["code"] == "unsafe_identifier"
    assert missing["status"] == "error"
    assert missing["code"] == "missing_table"


def test_server_registers_only_completed_milestone_three_tools(
    demo_database_path: Path,
) -> None:
    server = create_server(settings_for(demo_database_path))

    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == ["list_tables", "profile_table"]
