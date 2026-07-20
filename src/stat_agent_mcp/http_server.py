"""Railway-compatible Streamable HTTP entry point."""

from mcp.server.fastmcp import FastMCP
from pydantic import SecretStr
from starlette.types import ASGIApp

from stat_agent_mcp.config import (
    Settings,
    load_http_bearer_token,
    load_http_port,
    load_settings,
)
from stat_agent_mcp.connectors.demo_sqlite import ensure_demo_database
from stat_agent_mcp.http_auth import BearerAuthMiddleware
from stat_agent_mcp.server import create_server


def create_http_server(
    settings: Settings | None = None,
    *,
    port: int | None = None,
) -> FastMCP:
    """Bootstrap demo data and compose the stateless Streamable HTTP server."""
    resolved_settings = load_settings() if settings is None else settings
    ensure_demo_database(resolved_settings.sqlite_path())
    return create_server(
        resolved_settings,
        host="0.0.0.0",
        port=load_http_port() if port is None else port,
        json_response=True,
        stateless_http=True,
    )


def create_http_application(
    settings: Settings | None = None,
    *,
    port: int | None = None,
    bearer_token: SecretStr | None = None,
) -> ASGIApp:
    """Compose a fail-closed bearer-protected Streamable HTTP application."""
    resolved_token = load_http_bearer_token() if bearer_token is None else bearer_token
    server = create_http_server(settings, port=port)
    return BearerAuthMiddleware(
        server.streamable_http_app(),
        resolved_token,
        protected_path=server.settings.streamable_http_path,
    )


def main() -> None:
    """Run the MCP server over stateless Streamable HTTP."""
    import uvicorn

    try:
        port = load_http_port()
        application = create_http_application(port=port)
    except ValueError:
        raise SystemExit("HTTP server configuration is invalid.") from None
    uvicorn.run(application, host="0.0.0.0", port=port)
