"""Read-only SQLite metadata connector."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final, Literal, cast

from stat_agent_mcp.connectors.base import TableMetadata
from stat_agent_mcp.errors import ConnectionFailureError

_LIST_TABLES_QUERY: Final = """
    SELECT name, type
    FROM sqlite_schema
    WHERE type IN ('table', 'view')
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
"""


class SQLiteConnector:
    """Provide fixed, read-only SQLite operations without arbitrary SQL access."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_tables(self) -> tuple[TableMetadata, ...]:
        """List user-defined tables and views in deterministic name order."""
        if not self._database_path.is_file():
            raise ConnectionFailureError

        try:
            with self._connect_read_only() as connection:
                rows = connection.execute(_LIST_TABLES_QUERY).fetchall()
        except sqlite3.Error:
            raise ConnectionFailureError from None

        return tuple(
            TableMetadata(
                name=str(row[0]),
                table_type=cast(Literal["table", "view"], str(row[1])),
            )
            for row in rows
        )

    def _connect_read_only(self) -> sqlite3.Connection:
        database_uri = f"{self._database_path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True)
        connection.execute("PRAGMA query_only = ON")
        return connection
