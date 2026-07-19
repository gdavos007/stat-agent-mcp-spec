"""MCP server composition and local stdio entry point."""

from mcp.server.fastmcp import FastMCP

from stat_agent_mcp.config import load_settings


def create_server() -> FastMCP:
    """Create the empty milestone-one MCP server after validating configuration."""
    settings = load_settings()
    return FastMCP(name=settings.connection_name)


def main() -> None:
    """Run the MCP server over stdio."""
    create_server().run(transport="stdio")

