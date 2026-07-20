"""Composition coverage for the Streamable HTTP MCP entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import SecretStr

from stat_agent_mcp.config import Settings
from stat_agent_mcp.server import create_server


def test_http_server_reuses_the_existing_tool_composition(
    demo_database_path: Path,
) -> None:
    settings = Settings(
        connection_name="http_demo",
        sqlite_path_secret=SecretStr(str(demo_database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )

    server = create_server(
        settings,
        host="0.0.0.0",  # noqa: S104 - required for Railway's external listener
        port=54321,
        json_response=True,
        stateless_http=True,
    )

    assert server.settings.host == "0.0.0.0"  # noqa: S104
    assert server.settings.port == 54321
    assert server.settings.json_response is True
    assert server.settings.stateless_http is True
    assert [tool.name for tool in asyncio.run(server.list_tools())] == [
        "list_tables",
        "profile_table",
        "run_test",
    ]
