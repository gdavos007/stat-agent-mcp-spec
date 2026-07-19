"""MCP tool registration functions."""

from stat_agent_mcp.tools.list_tables import register_list_tables
from stat_agent_mcp.tools.profile_table import register_profile_table

__all__ = ["register_list_tables", "register_profile_table"]
