"""Read-only SQLite metadata connector."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final, Literal, cast

import pandas as pd

from stat_agent_mcp.connectors.base import (
    BoundedExtraction,
    BoundedExtractionRequest,
    ColumnMetadata,
    ExtractionMetadata,
    TableDescription,
    TableMetadata,
)
from stat_agent_mcp.connectors.identifiers import ValidatedIdentifier
from stat_agent_mcp.errors import (
    ConnectionFailureError,
    DeterministicOrderingUnavailableError,
    ExtractionLimitError,
    MissingColumnError,
    MissingTableError,
)

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

    def describe_table(self, table: ValidatedIdentifier) -> TableDescription:
        """Return columns and a stable primary-key or rowid ordering strategy."""
        try:
            with self._connect_read_only() as connection:
                relation = connection.execute(
                    """
                    SELECT type, sql
                    FROM sqlite_schema
                    WHERE name = ? AND type IN ('table', 'view')
                    """,
                    (table.value,),
                ).fetchone()
                if relation is None:
                    raise MissingTableError
                column_rows = connection.execute(
                    """
                    SELECT name, type, "notnull", pk
                    FROM pragma_table_info(?)
                    ORDER BY cid
                    """,
                    (table.value,),
                ).fetchall()
        except (MissingTableError, DeterministicOrderingUnavailableError):
            raise
        except sqlite3.Error:
            raise ConnectionFailureError from None

        table_type = cast(Literal["table", "view"], str(relation[0]))
        columns = tuple(
            ColumnMetadata(
                name=str(row[0]),
                database_type=str(row[1] or ""),
                nullable=not bool(row[2]) and not bool(row[3]),
                primary_key_position=int(row[3]) or None,
            )
            for row in column_rows
        )
        order_columns = self._deterministic_order(table_type, relation[1], columns)
        return TableDescription(
            name=table.value,
            table_type=table_type,
            columns=columns,
            order_columns=order_columns,
        )

    def extract(self, request: BoundedExtractionRequest) -> BoundedExtraction:
        """Extract selected columns using a stable order and a limit sentinel."""
        if request.limit <= 0 or request.hard_limit <= 0 or request.limit > request.hard_limit:
            raise ExtractionLimitError
        if not request.columns:
            raise MissingColumnError

        description = self.describe_table(request.table)
        available_columns = {column.name for column in description.columns}
        if any(column.value not in available_columns for column in request.columns):
            raise MissingColumnError

        selected_sql = ", ".join(self._quote(column.value) for column in request.columns)
        order_sql = ", ".join(self._quote(column) for column in description.order_columns)
        query = (
            f"SELECT {selected_sql} FROM {self._quote(request.table.value)} "
            f"ORDER BY {order_sql} LIMIT ?"
        )
        try:
            with self._connect_read_only() as connection:
                rows = connection.execute(query, (request.limit + 1,)).fetchall()
        except sqlite3.Error:
            raise ConnectionFailureError from None

        truncated = len(rows) > request.limit
        retained_rows = rows[: request.limit]
        frame = pd.DataFrame.from_records(
            retained_rows,
            columns=[column.value for column in request.columns],
        )
        return BoundedExtraction(
            frame=frame,
            metadata=ExtractionMetadata(
                requested_limit=(
                    request.limit if request.requested_limit is None else request.requested_limit
                ),
                effective_limit=request.limit,
                hard_limit=request.hard_limit,
                rows_examined=len(retained_rows),
                truncated=truncated,
                sampled=False,
                sampling_method="none",
                random_seed=None,
                order_columns=description.order_columns,
            ),
        )

    def _connect_read_only(self) -> sqlite3.Connection:
        database_uri = f"{self._database_path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True)
        try:
            connection.execute("PRAGMA query_only = ON")
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    @staticmethod
    def _quote(identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'

    @staticmethod
    def _deterministic_order(
        table_type: Literal["table", "view"],
        create_sql: object,
        columns: tuple[ColumnMetadata, ...],
    ) -> tuple[str, ...]:
        primary_key = tuple(
            column.name
            for column in sorted(
                (column for column in columns if column.primary_key_position is not None),
                key=lambda column: cast(int, column.primary_key_position),
            )
        )
        if primary_key:
            return primary_key

        sql_text = str(create_sql or "").upper()
        if table_type == "table" and "WITHOUT ROWID" not in sql_text:
            column_names = {column.name.casefold() for column in columns}
            for alias in ("rowid", "_rowid_", "oid"):
                if alias.casefold() not in column_names:
                    return (alias,)
        raise DeterministicOrderingUnavailableError
