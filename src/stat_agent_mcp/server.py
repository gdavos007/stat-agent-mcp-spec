"""MCP server composition and local stdio entry point."""

from mcp.server.fastmcp import FastMCP

from stat_agent_mcp.config import Settings, load_settings
from stat_agent_mcp.connectors.sqlite import SQLiteConnector
from stat_agent_mcp.services.extraction import ExtractionService
from stat_agent_mcp.services.profiling import ProfilingService
from stat_agent_mcp.tools.list_tables import register_list_tables
from stat_agent_mcp.tools.profile_table import register_profile_table


def create_server(settings: Settings | None = None) -> FastMCP:
    """Compose the MCP server and its single completed table-discovery tool."""
    resolved_settings = load_settings() if settings is None else settings
    server = FastMCP(name=resolved_settings.connection_name)
    connector = SQLiteConnector(resolved_settings.sqlite_path())
    register_list_tables(server, connector, resolved_settings.connection_name)
    extraction_service = ExtractionService(
        connector,
        default_limit=resolved_settings.default_row_limit,
        hard_limit=resolved_settings.hard_row_limit,
    )
    profiling_service = ProfilingService(extraction_service)
    register_profile_table(server, profiling_service, resolved_settings.connection_name)
    return server


def main() -> None:
    """Run the MCP server over stdio."""
    create_server().run(transport="stdio")
