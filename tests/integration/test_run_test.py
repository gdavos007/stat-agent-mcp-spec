"""Integration tests for the Welch run_test MCP vertical slice."""

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest
from mcp.server.fastmcp import FastMCP
from pydantic import SecretStr

from stat_agent_mcp.config import Settings
from stat_agent_mcp.server import create_server


def settings_for(
    database_path: Path,
    *,
    default_limit: int = 100,
    hard_limit: int = 1_000,
) -> Settings:
    return Settings(
        connection_name="demo_sqlite",
        sqlite_path_secret=SecretStr(str(database_path)),
        default_row_limit=default_limit,
        hard_row_limit=hard_limit,
    )


def structured_result(
    server: FastMCP,
    arguments: dict[str, object],
) -> dict[str, Any]:
    raw_result = asyncio.run(server.call_tool("run_test", arguments))
    assert isinstance(raw_result, tuple)
    _, structured = raw_result
    return cast(dict[str, Any], structured["result"])


def welch_arguments(**overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "test_id": "welch_t_test",
        "table": "experiment_results",
        "outcome_column": "account_balance",
        "grouping_column": "variant",
        "group_values": ["A", "B"],
        "alpha": 0.05,
    }
    arguments.update(overrides)
    return arguments


def test_run_test_returns_auditable_welch_result(demo_database_path: Path) -> None:
    server = create_server(settings_for(demo_database_path))

    response = structured_result(server, welch_arguments())
    result = response["result"]

    assert response["status"] == "success"
    assert result["test_id"] == "welch_t_test"
    assert result["test_name"] == "Welch's independent two-sample t-test"
    assert result["alpha"] == 0.05
    assert result["significant"] is True
    assert 0.0 <= result["p_value"] <= 1.0
    assert result["effect_size_name"] == "hedges_g"
    assert result["effect_size"] < 0
    assert [summary["sample_size"] for summary in result["group_summaries"]] == [19, 19]
    assert result["rows_examined"] == 40
    assert result["rows_included"] == 38
    assert result["null_rows_excluded"] == 2
    assert result["invalid_rows_excluded"] == 0
    assert result["unselected_group_rows_excluded"] == 0
    assert result["extraction"]["truncated"] is False


def test_run_test_warns_when_first_n_extraction_is_truncated(
    demo_database_path: Path,
) -> None:
    server = create_server(settings_for(demo_database_path, default_limit=30, hard_limit=30))

    response = structured_result(server, welch_arguments(max_rows=500))
    result = response["result"]

    assert response["status"] == "success"
    assert result["extraction"]["effective_limit"] == 30
    assert result["extraction"]["truncated"] is True
    assert any("first-N" in warning for warning in result["warnings"])


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"test_id": "two_proportion_z_test"}, "unsupported_test"),
        ({"outcome_column": "missing_column"}, "missing_column"),
        ({"group_values": ["A", "A"]}, "invalid_group_values"),
        ({"alpha": 1.5}, "invalid_request"),
        ({"outcome_column": "variant", "grouping_column": "converted"}, "incompatible_column_type"),
    ],
)
def test_run_test_returns_structured_errors(
    demo_database_path: Path,
    overrides: dict[str, object],
    expected_code: str,
) -> None:
    server = create_server(settings_for(demo_database_path))

    response = structured_result(server, welch_arguments(**overrides))

    assert response["status"] == "error"
    assert response["code"] == expected_code


def test_server_registers_exactly_three_mvp_tools(demo_database_path: Path) -> None:
    server = create_server(settings_for(demo_database_path))

    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == ["list_tables", "profile_table", "run_test"]
    run_test_tool = tools[2]
    assert run_test_tool.outputSchema is not None
    assert "Welch" in (run_test_tool.description or "")
    assert "null" in (run_test_tool.description or "").lower()
    assert "hard row limit" in (run_test_tool.description or "").lower()
