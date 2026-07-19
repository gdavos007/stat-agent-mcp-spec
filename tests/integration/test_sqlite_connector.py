"""Integration tests for read-only SQLite metadata discovery."""

from pathlib import Path

import pytest

from stat_agent_mcp.connectors.base import DatabaseConnector
from stat_agent_mcp.connectors.sqlite import SQLiteConnector
from stat_agent_mcp.errors import ConnectionFailureError


def test_sqlite_connector_lists_seeded_tables(demo_database_path: Path) -> None:
    connector: DatabaseConnector = SQLiteConnector(demo_database_path)

    tables = connector.list_tables()

    assert [(table.name, table.table_type) for table in tables] == [
        ("experiment_results", "table")
    ]
    assert not hasattr(connector, "execute")


def test_sqlite_connector_reports_missing_database_without_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "sensitive-customer-name.sqlite3"
    connector = SQLiteConnector(missing_path)

    with pytest.raises(ConnectionFailureError) as caught:
        connector.list_tables()

    assert str(missing_path) not in str(caught.value)
    assert not missing_path.exists()
