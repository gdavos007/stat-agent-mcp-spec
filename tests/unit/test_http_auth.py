"""Tests for the controlled-demo HTTP bearer boundary."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr
from starlette.responses import Response
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from stat_agent_mcp.http_auth import BearerAuthMiddleware

CONFIGURED_TOKEN = "test-only-7VvQw3j9L2m6Nc8Rx4Za1Bp5Ty0Hd7Ks"


async def reachable_app(scope: Scope, receive: Receive, send: Send) -> None:
    """Return a distinctive response when authentication reaches the application."""
    await Response(status_code=204)(scope, receive, send)


def test_missing_authentication_returns_generic_unauthorized_response() -> None:
    client = TestClient(BearerAuthMiddleware(reachable_app, SecretStr(CONFIGURED_TOKEN)))

    response = client.post("/mcp")

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    [
        "Basic dGVzdDp0ZXN0",
        "Bearer",
        "Bearer ",
        "Bearer incorrect-test-only-M4pQ8xN2cV6kL0sJ7hD3fW9z",
        f"Bearer {CONFIGURED_TOKEN} trailing-data",
    ],
)
def test_invalid_authentication_uses_the_same_unauthorized_contract(
    authorization: str,
) -> None:
    client = TestClient(BearerAuthMiddleware(reachable_app, SecretStr(CONFIGURED_TOKEN)))

    response = client.post("/mcp", headers={"Authorization": authorization})

    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert CONFIGURED_TOKEN not in response.text
    assert authorization not in response.text


def test_valid_bearer_authentication_reaches_application() -> None:
    client = TestClient(BearerAuthMiddleware(reachable_app, SecretStr(CONFIGURED_TOKEN)))

    response = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {CONFIGURED_TOKEN}"},
    )

    assert response.status_code == 204


def test_authentication_protects_mcp_subpaths_but_not_future_public_routes() -> None:
    client = TestClient(BearerAuthMiddleware(reachable_app, SecretStr(CONFIGURED_TOKEN)))

    assert client.get("/mcp/events").status_code == 401
    assert client.get("/health").status_code == 204
    assert client.get("/mcp-adjacent").status_code == 204


def test_authentication_does_not_log_or_write_tokens(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    supplied_token = "incorrect-test-only-M4pQ8xN2cV6kL0sJ7hD3fW9z"
    client = TestClient(BearerAuthMiddleware(reachable_app, SecretStr(CONFIGURED_TOKEN)))

    with caplog.at_level(logging.DEBUG):
        response = client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {supplied_token}"},
        )

    captured = capsys.readouterr()
    exposed_text = f"{caplog.text}{captured.out}{captured.err}{response.text}"
    assert CONFIGURED_TOKEN not in exposed_text
    assert supplied_token not in exposed_text
