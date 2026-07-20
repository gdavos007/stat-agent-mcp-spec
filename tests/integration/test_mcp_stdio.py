"""End-to-end coverage for the installed MCP server over stdio."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult


def _payload(result: CallToolResult) -> dict[str, Any]:
    """Return the public tool payload from MCP 1.28 structured content."""
    assert result.isError is False
    assert result.structuredContent is not None
    assert set(result.structuredContent) == {"result"}
    payload = result.structuredContent["result"]
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _assert_secret_absent(secret: str, values: object) -> None:
    """Check redaction without reproducing a secret in assertion output."""
    serialized = json.dumps(values, default=str, sort_keys=True)
    if secret in serialized:
        raise AssertionError("Sensitive configuration appeared in MCP output.")


def test_installed_server_operates_end_to_end_over_stdio(
    demo_database_path: Path,
) -> None:
    """Exercise every MVP tool through a real MCP client and subprocess."""

    async def exercise_server() -> None:
        entry_point = Path(sys.executable).with_name("stat-agent-mcp")
        assert entry_point.is_file(), "Installed stat-agent-mcp entry point was not found."

        database_path = str(demo_database_path)
        source_path = Path(__file__).parents[2] / "src"
        server_parameters = StdioServerParameters(
            command=str(entry_point),
            env={
                # Match pytest's declared src-layout import path when the active
                # runtime skips Hatchling's hidden editable-install .pth file.
                "PYTHONPATH": str(source_path),
                "STAT_MCP_CONNECTION_NAME": "stdio_demo",
                "STAT_MCP_SQLITE_PATH": database_path,
                "STAT_MCP_DEFAULT_ROW_LIMIT": "100",
                "STAT_MCP_HARD_ROW_LIMIT": "1000",
            },
        )
        observed_results: list[dict[str, Any]] = []

        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as captured_stderr:
            async with stdio_client(server_parameters, errlog=captured_stderr) as streams:
                read_stream, write_stream = streams
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=15),
                ) as session:
                    await session.initialize()

                    tools = await session.list_tools()
                    assert [tool.name for tool in tools.tools] == [
                        "list_tables",
                        "profile_table",
                        "run_test",
                    ]

                    list_result = await session.call_tool("list_tables", {})
                    listed = _payload(list_result)
                    observed_results.append(list_result.model_dump(mode="json"))
                    assert listed == {
                        "status": "success",
                        "connection_name": "stdio_demo",
                        "database_engine": "sqlite",
                        "tables": [
                            {"name": "experiment_results", "table_type": "table"},
                        ],
                    }

                    profile_result = await session.call_tool(
                        "profile_table",
                        {"table": "experiment_results"},
                    )
                    profile = _payload(profile_result)
                    observed_results.append(profile_result.model_dump(mode="json"))
                    assert profile["status"] == "success"
                    assert profile["table_name"] == "experiment_results"
                    assert profile["row_count_considered"] == 40
                    assert profile["extraction"]["truncated"] is False
                    columns = {column["name"]: column for column in profile["columns"]}
                    assert columns["account_balance"]["suggested_role"] == "continuous_outcome"
                    assert columns["account_balance"]["null_count"] == 2
                    assert columns["converted"]["suggested_role"] == "binary_outcome"
                    assert columns["converted"]["null_count"] == 2

                    welch_result = await session.call_tool(
                        "run_test",
                        {
                            "test_id": "welch_t_test",
                            "table": "experiment_results",
                            "outcome_column": "account_balance",
                            "grouping_column": "variant",
                            "group_values": ["A", "B"],
                            "alpha": 0.05,
                        },
                    )
                    welch_response = _payload(welch_result)
                    observed_results.append(welch_result.model_dump(mode="json"))
                    assert welch_response["status"] == "success"
                    welch = welch_response["result"]
                    assert welch["test_id"] == "welch_t_test"
                    assert welch["effect_size_name"] == "hedges_g"
                    assert welch["effect_size"] < 0
                    assert welch["rows_examined"] == 40
                    assert welch["rows_included"] == 38
                    assert welch["null_rows_excluded"] == 2
                    assert [group["sample_size"] for group in welch["group_summaries"]] == [19, 19]

                    proportion_result = await session.call_tool(
                        "run_test",
                        {
                            "test_id": "two_proportion_z_test",
                            "table": "experiment_results",
                            "outcome_column": "converted",
                            "grouping_column": "variant",
                            "group_values": ["A", "B"],
                            "success_value": 1,
                            "alpha": 0.05,
                        },
                    )
                    proportion_response = _payload(proportion_result)
                    observed_results.append(proportion_result.model_dump(mode="json"))
                    assert proportion_response["status"] == "success"
                    proportion = proportion_response["result"]
                    assert proportion["test_id"] == "two_proportion_z_test"
                    assert proportion["success_value"] == 1
                    assert proportion["effect_size_name"] == "risk_difference"
                    assert proportion["effect_size"] < 0
                    assert proportion["rows_examined"] == 40
                    assert proportion["rows_included"] == 38
                    assert proportion["null_rows_excluded"] == 2
                    assert [group["successes"] for group in proportion["group_summaries"]] == [
                        6,
                        10,
                    ]

                    error_result = await session.call_tool(
                        "profile_table",
                        {"table": "missing_table"},
                    )
                    error = _payload(error_result)
                    observed_results.append(error_result.model_dump(mode="json"))
                    assert error == {
                        "status": "error",
                        "code": "missing_table",
                        "message": "The requested table does not exist.",
                        "retryable": False,
                    }

                    second_list_result = await session.call_tool("list_tables", {})
                    second_list = _payload(second_list_result)
                    observed_results.append(second_list_result.model_dump(mode="json"))
                    assert second_list == listed

            captured_stderr.seek(0)
            stderr = captured_stderr.read()

        _assert_secret_absent(database_path, observed_results)
        _assert_secret_absent(database_path, stderr)

    asyncio.run(exercise_server())
