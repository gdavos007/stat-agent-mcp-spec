"""Composition coverage for the Streamable HTTP MCP entry point."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest
from pydantic import SecretStr
from starlette.testclient import TestClient

from stat_agent_mcp.config import Settings
from stat_agent_mcp.http_server import create_http_application, create_http_server
from stat_agent_mcp.server import create_server

HTTP_TOKEN = "test-only-3pV8mK1xQ7dN4sR9wL2cF6jH0tZ5bY7G"


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


def test_http_startup_bootstraps_an_absent_demo_database(tmp_path: Path) -> None:
    database_path = tmp_path / "railway" / "demo.sqlite3"
    settings = Settings(
        connection_name="railway_demo",
        sqlite_path_secret=SecretStr(str(database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )

    server = create_http_server(settings, port=54321)

    assert database_path.is_file()
    assert server.settings.host == "0.0.0.0"  # noqa: S104
    assert server.settings.port == 54321


@pytest.mark.parametrize("token_value", [None, "   "])
def test_http_application_fails_closed_without_token(
    demo_database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    token_value: str | None,
) -> None:
    settings = Settings(
        connection_name="railway_demo",
        sqlite_path_secret=SecretStr(str(demo_database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )
    if token_value is None:
        monkeypatch.delenv("STAT_MCP_HTTP_BEARER_TOKEN", raising=False)
    else:
        monkeypatch.setenv("STAT_MCP_HTTP_BEARER_TOKEN", token_value)

    with pytest.raises(ValueError, match="STAT_MCP_HTTP_BEARER_TOKEN"):
        create_http_application(settings, port=54321)


def test_authenticated_request_reaches_streamable_http_mcp_application(
    demo_database_path: Path,
) -> None:
    settings = Settings(
        connection_name="authenticated_demo",
        sqlite_path_secret=SecretStr(str(demo_database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )
    application = create_http_application(
        settings,
        port=54321,
        bearer_token=SecretStr(HTTP_TOKEN),
    )

    with TestClient(application) as client:
        response = client.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {HTTP_TOKEN}",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "integration-test", "version": "1.0"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "authenticated_demo"


def test_streamable_http_application_rejects_missing_authentication(
    demo_database_path: Path,
) -> None:
    settings = Settings(
        connection_name="authenticated_demo",
        sqlite_path_secret=SecretStr(str(demo_database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )
    application = create_http_application(
        settings,
        port=54321,
        bearer_token=SecretStr(HTTP_TOKEN),
    )

    with TestClient(application) as client:
        response = client.post("/mcp")

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert HTTP_TOKEN not in response.text


def test_health_endpoint_is_public_and_minimal(demo_database_path: Path) -> None:
    settings = Settings(
        connection_name="health_demo",
        sqlite_path_secret=SecretStr(str(demo_database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )
    application = create_http_application(
        settings,
        port=54321,
        bearer_token=SecretStr(HTTP_TOKEN),
    )

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert set(response.json()) == {"status"}


def test_http_startup_logs_lifecycle_without_private_configuration(
    demo_database_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(
        connection_name="log_demo",
        sqlite_path_secret=SecretStr(str(demo_database_path)),
        default_row_limit=100,
        hard_row_limit=1_000,
    )

    with caplog.at_level(logging.INFO, logger="stat_agent_mcp.http_server"):
        application = create_http_application(
            settings,
            port=54321,
            bearer_token=SecretStr(HTTP_TOKEN),
        )
        with TestClient(application):
            pass

    assert caplog.messages == [
        "HTTP server starting host=0.0.0.0 port=54321 mcp_endpoint=/mcp",
        "Demo database bootstrap successful mode=reused",
        "HTTP server ready",
    ]
    assert str(demo_database_path) not in caplog.text
    assert HTTP_TOKEN not in caplog.text
