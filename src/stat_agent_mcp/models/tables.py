"""Public models for the list_tables MCP tool."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from stat_agent_mcp.models.common import ToolError


class TableInfo(BaseModel):
    """Safe public metadata for one table or view."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    table_type: Literal["table", "view"]


class ListTablesSuccess(BaseModel):
    """Successful list_tables response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["success"] = "success"
    connection_name: str
    database_engine: Literal["sqlite"] = "sqlite"
    tables: tuple[TableInfo, ...]


ListTablesResponse = Annotated[ListTablesSuccess | ToolError, Field(discriminator="status")]
