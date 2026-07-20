"""Railway-compatible Streamable HTTP entry point."""

from mcp.server.fastmcp import FastMCP

from stat_agent_mcp.config import Settings, load_http_port, load_settings
from stat_agent_mcp.connectors.demo_sqlite import ensure_demo_database
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


def main() -> None:
    """Run the MCP server over stateless Streamable HTTP."""
    create_http_server().run(transport="streamable-http")
