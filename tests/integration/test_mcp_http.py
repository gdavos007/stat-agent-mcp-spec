"""End-to-end coverage for the installed MCP server over Streamable HTTP."""

from __future__ import annotations

import asyncio
import json
import signal
import socket
import sys
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

TEST_BEARER_TOKEN = "test-only-H7vN2qL9xR4mK8cT1zW6pD3sF0bY5jQ7"


def _payload(result: CallToolResult) -> dict[str, Any]:
    """Return the public tool payload from MCP 1.28 structured content."""
    assert result.isError is False
    assert result.structuredContent is not None
    assert set(result.structuredContent) == {"result"}
    payload = result.structuredContent["result"]
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _available_tcp_port() -> int:
    """Ask the operating system for an available loopback TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def _wait_until_ready(process: asyncio.subprocess.Process, url: str) -> httpx.Response:
    """Poll the public health endpoint within a fixed deadline."""
    async with httpx.AsyncClient(timeout=0.5, trust_env=False) as client:
        for _ in range(60):
            if process.returncode is not None:
                raise AssertionError("Installed HTTP server exited before becoming ready.")
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return response
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.1)
    raise AssertionError("Installed HTTP server did not become ready before the deadline.")


async def _stop_process(process: asyncio.subprocess.Process) -> tuple[bytes, bytes]:
    """Terminate the child and collect output without allowing an indefinite wait."""
    if process.returncode is None:
        process.send_signal(signal.SIGINT)
    try:
        return await asyncio.wait_for(process.communicate(), timeout=10)
    except TimeoutError:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            return await asyncio.wait_for(process.communicate(), timeout=5)
        except TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
        return await asyncio.wait_for(process.communicate(), timeout=5)


def _assert_private_values_absent(private_values: list[str], observed: object) -> None:
    """Assert redaction without reproducing private values in failure output."""
    serialized = json.dumps(observed, default=str, sort_keys=True)
    if any(private_value in serialized for private_value in private_values):
        raise AssertionError("Private HTTP configuration appeared in observed output.")


def test_installed_server_operates_end_to_end_over_streamable_http(tmp_path: Path) -> None:
    """Exercise every MVP tool through the installed authenticated HTTP process."""

    async def exercise_server() -> None:
        entry_point = Path(sys.executable).with_name("stat-agent-mcp-http")
        assert entry_point.is_file(), "Installed stat-agent-mcp-http entry point was not found."

        port = _available_tcp_port()
        database_path = tmp_path / "bootstrap" / "demo.sqlite3"
        endpoint = f"http://127.0.0.1:{port}/mcp"
        health_endpoint = f"http://127.0.0.1:{port}/health"
        server_environment = {
            "PORT": str(port),
            "STAT_MCP_CONNECTION_NAME": "http_demo",
            "STAT_MCP_SQLITE_PATH": str(database_path),
            "STAT_MCP_HTTP_BEARER_TOKEN": TEST_BEARER_TOKEN,
        }
        process = await asyncio.create_subprocess_exec(
            str(entry_point),
            cwd=tmp_path,
            env=server_environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        observed_http: list[object] = []
        observed_mcp: list[object] = []

        try:
            readiness = await _wait_until_ready(process, health_endpoint)
            observed_http.append(
                {
                    "status": readiness.status_code,
                    "headers": dict(readiness.headers),
                    "body": readiness.text,
                }
            )
            assert readiness.json() == {"status": "ok"}

            async with httpx.AsyncClient(timeout=2, trust_env=False) as public_client:
                unauthorized = await public_client.post(endpoint)
            observed_http.append(
                {
                    "status": unauthorized.status_code,
                    "headers": dict(unauthorized.headers),
                    "body": unauthorized.text,
                }
            )
            assert unauthorized.status_code == 401
            assert unauthorized.headers["www-authenticate"] == "Bearer"
            assert unauthorized.json() == {"error": "unauthorized"}

            async with (
                httpx.AsyncClient(
                    headers={"Authorization": f"Bearer {TEST_BEARER_TOKEN}"},
                    timeout=10,
                    trust_env=False,
                ) as authenticated_client,
                streamable_http_client(
                    endpoint,
                    http_client=authenticated_client,
                ) as streams,
                ClientSession(
                    streams[0],
                    streams[1],
                    read_timeout_seconds=timedelta(seconds=15),
                ) as session,
            ):
                await session.initialize()

                tools = await session.list_tools()
                assert [tool.name for tool in tools.tools] == [
                    "list_tables",
                    "profile_table",
                    "run_test",
                ]

                list_result = await session.call_tool("list_tables", {})
                listed = _payload(list_result)
                observed_mcp.append(list_result.model_dump(mode="json"))
                assert listed == {
                    "status": "success",
                    "connection_name": "http_demo",
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
                observed_mcp.append(profile_result.model_dump(mode="json"))
                assert profile["status"] == "success"
                assert profile["table_name"] == "experiment_results"
                assert profile["row_count_considered"] == 40
                assert [column["name"] for column in profile["columns"]] == [
                    "record_id",
                    "variant",
                    "account_balance",
                    "converted",
                ]
                assert profile["extraction"]["effective_limit"] == 1_000
                assert profile["extraction"]["hard_limit"] == 10_000
                assert profile["extraction"]["truncated"] is False
                assert profile["extraction"]["sampled"] is False

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
                observed_mcp.append(welch_result.model_dump(mode="json"))
                assert welch_response["status"] == "success"
                welch = welch_response["result"]
                assert welch["statistic"] == pytest.approx(-13.947136964053161)
                assert welch["p_value"] == pytest.approx(4.3844422644743503e-16)
                assert welch["effect_size"] == pytest.approx(-4.43011766520242)
                assert welch["rows_included"] == 38
                assert welch["null_rows_excluded"] == 2

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
                observed_mcp.append(proportion_result.model_dump(mode="json"))
                assert proportion_response["status"] == "success"
                proportion = proportion_response["result"]
                assert proportion["statistic"] == pytest.approx(-1.3142574813455417)
                assert proportion["p_value"] == pytest.approx(0.1887595705411257)
                assert proportion["effect_size"] == pytest.approx(-4 / 19)
                assert [group["successes"] for group in proportion["group_summaries"]] == [
                    6,
                    10,
                ]

                error_result = await session.call_tool(
                    "profile_table",
                    {"table": "missing_table"},
                )
                error = _payload(error_result)
                observed_mcp.append(error_result.model_dump(mode="json"))
                assert error == {
                    "status": "error",
                    "code": "missing_table",
                    "message": "The requested table does not exist.",
                    "retryable": False,
                }

                second_list_result = await session.call_tool("list_tables", {})
                observed_mcp.append(second_list_result.model_dump(mode="json"))
                assert _payload(second_list_result) == listed
        finally:
            stdout_bytes, stderr_bytes = await _stop_process(process)

        assert process.returncode == 0
        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")
        assert "Traceback" not in stderr
        assert "HTTP server starting host=0.0.0.0" in stderr
        assert "Demo database bootstrap successful mode=created" in stderr
        assert "HTTP server ready" in stderr
        private_values = [
            str(database_path),
            TEST_BEARER_TOKEN,
            "STAT_MCP_CONNECTION_NAME",
            "STAT_MCP_SQLITE_PATH",
            "STAT_MCP_HTTP_BEARER_TOKEN",
            "PORT",
        ]
        _assert_private_values_absent(private_values, observed_http)
        _assert_private_values_absent(private_values, observed_mcp)
        _assert_private_values_absent(private_values, stdout)
        _assert_private_values_absent(private_values, stderr)

    asyncio.run(exercise_server())


def test_installed_http_server_handles_sigterm_cleanly(tmp_path: Path) -> None:
    """Verify Railway's module command and normal termination signal."""

    async def exercise_sigterm() -> None:
        port = _available_tcp_port()
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "stat_agent_mcp.http_server",
            cwd=tmp_path,
            env={
                "PORT": str(port),
                "STAT_MCP_CONNECTION_NAME": "sigterm_demo",
                "STAT_MCP_SQLITE_PATH": str(tmp_path / "sigterm" / "demo.sqlite3"),
                "STAT_MCP_HTTP_BEARER_TOKEN": TEST_BEARER_TOKEN,
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await _wait_until_ready(process, f"http://127.0.0.1:{port}/health")
            process.send_signal(signal.SIGTERM)
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=10)
        finally:
            if process.returncode is None:
                await _stop_process(process)

        assert process.returncode == 0
        output = f"{stdout_bytes.decode(errors='replace')}{stderr_bytes.decode(errors='replace')}"
        assert "Traceback" not in output
        assert output.count("Shutting down") == 1

    asyncio.run(exercise_sigterm())
