"""Railway-compatible Streamable HTTP entry point."""

from stat_agent_mcp.config import load_http_port
from stat_agent_mcp.server import create_server


def main() -> None:
    """Run the MCP server over stateless Streamable HTTP."""
    create_server(
        host="0.0.0.0",
        port=load_http_port(),
        json_response=True,
        stateless_http=True,
    ).run(transport="streamable-http")
