"""MCP server composition and local stdio entry point."""

from mcp.server.fastmcp import FastMCP

from stat_agent_mcp.config import Settings, load_settings
from stat_agent_mcp.connectors.sqlite import SQLiteConnector
from stat_agent_mcp.tools.list_tables import register_list_tables


def create_server(settings: Settings | None = None) -> FastMCP:
    """Compose the MCP server and its single completed table-discovery tool."""
    resolved_settings = load_settings() if settings is None else settings
    server = FastMCP(name=resolved_settings.connection_name)
    connector = SQLiteConnector(resolved_settings.sqlite_path())
    register_list_tables(server, connector, resolved_settings.connection_name)
    return server


def main() -> None:
    """Run the MCP server over stdio."""
    create_server().run(transport="stdio")
