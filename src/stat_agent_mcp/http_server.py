"""Railway-compatible Streamable HTTP entry point."""

import logging
import signal
from types import FrameType
from typing import NoReturn

from mcp.server.fastmcp import FastMCP
from pydantic import SecretStr
from starlette.types import ASGIApp

from stat_agent_mcp.config import (
    HTTP_BEARER_TOKEN_ENV,
    HTTP_PORT_ENV,
    SQLITE_PATH_ENV,
    Settings,
    load_http_bearer_token,
    load_http_port,
    load_settings,
)
from stat_agent_mcp.connectors.demo_sqlite import ensure_demo_database
from stat_agent_mcp.health import register_health_route
from stat_agent_mcp.http_auth import BearerAuthMiddleware
from stat_agent_mcp.http_lifecycle import ReadinessLoggingMiddleware
from stat_agent_mcp.server import create_server

LOGGER = logging.getLogger(__name__)
HTTP_HOST = "0.0.0.0"
MCP_ENDPOINT = "/mcp"


def _exit_successfully_on_sigterm(_signal_number: int, _frame: FrameType | None) -> NoReturn:
    """Normalize Uvicorn's post-shutdown SIGTERM re-raise to a successful exit."""
    raise SystemExit(0)


def _safe_configuration_error(error: ValueError) -> str:
    """Describe a startup configuration category without printing names or values."""
    message = str(error)
    if HTTP_BEARER_TOKEN_ENV in message:
        return "HTTP bearer token is missing or invalid."
    if HTTP_PORT_ENV in message:
        return "HTTP port is invalid."
    if SQLITE_PATH_ENV in message:
        return "SQLite configuration is missing or invalid."
    return "server configuration is invalid."


def create_http_server(
    settings: Settings | None = None,
    *,
    port: int | None = None,
) -> FastMCP:
    """Bootstrap demo data and compose the stateless Streamable HTTP server."""
    resolved_settings = load_settings() if settings is None else settings
    database_created = ensure_demo_database(resolved_settings.sqlite_path())
    LOGGER.info(
        "Demo database bootstrap successful mode=%s",
        "created" if database_created else "reused",
    )
    server = create_server(
        resolved_settings,
        host=HTTP_HOST,
        port=load_http_port() if port is None else port,
        json_response=True,
        stateless_http=True,
    )
    register_health_route(server)
    return server


def create_http_application(
    settings: Settings | None = None,
    *,
    port: int | None = None,
    bearer_token: SecretStr | None = None,
) -> ASGIApp:
    """Compose a fail-closed bearer-protected Streamable HTTP application."""
    resolved_token = load_http_bearer_token() if bearer_token is None else bearer_token
    resolved_port = load_http_port() if port is None else port
    LOGGER.info(
        "HTTP server starting host=%s port=%d mcp_endpoint=%s",
        HTTP_HOST,
        resolved_port,
        MCP_ENDPOINT,
    )
    server = create_http_server(settings, port=resolved_port)
    return BearerAuthMiddleware(
        ReadinessLoggingMiddleware(server.streamable_http_app(), LOGGER),
        resolved_token,
        protected_path=server.settings.streamable_http_path,
    )


def main() -> None:
    """Run the MCP server over stateless Streamable HTTP."""
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        port = load_http_port()
        application = create_http_application(port=port)
    except ValueError as error:
        safe_error = _safe_configuration_error(error)
        raise SystemExit(f"HTTP server configuration error: {safe_error}") from None
    except OSError:
        raise SystemExit("HTTP server startup error: database bootstrap failed.") from None
    previous_sigterm_handler = signal.signal(signal.SIGTERM, _exit_successfully_on_sigterm)
    try:
        uvicorn.run(application, host=HTTP_HOST, port=port)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm_handler)


if __name__ == "__main__":
    main()
