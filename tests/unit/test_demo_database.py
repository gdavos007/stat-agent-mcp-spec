"""Tests for deterministic demo database creation and startup bootstrap."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from stat_agent_mcp.connectors.demo_sqlite import ensure_demo_database


def test_first_bootstrap_creates_parent_directories_and_demo_database(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "demo.sqlite3"

    created = ensure_demo_database(database_path)

    assert created is True
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM experiment_results").fetchone() == (40,)


def test_subsequent_bootstrap_reuses_a_valid_existing_database(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.sqlite3"
    ensure_demo_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE reuse_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO reuse_marker VALUES ('preserved')")

    created = ensure_demo_database(database_path)

    assert created is False
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT value FROM reuse_marker").fetchone() == ("preserved",)


def test_failed_generation_leaves_no_target_or_temporary_file(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.sqlite3"

    def fail_after_partial_write(temporary_path: Path) -> None:
        temporary_path.write_bytes(b"partial")
        raise RuntimeError("simulated generation failure")

    with pytest.raises(RuntimeError, match="simulated generation failure"):
        ensure_demo_database(database_path, generator=fail_after_partial_write)

    assert not database_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_generated_demo_rows_are_deterministic(tmp_path: Path) -> None:
    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"
    ensure_demo_database(first_path)
    ensure_demo_database(second_path)

    def read_rows(database_path: Path) -> list[tuple[object, ...]]:
        with sqlite3.connect(database_path) as connection:
            return connection.execute(
                """
                SELECT record_id, variant, account_balance, converted
                FROM experiment_results
                ORDER BY record_id
                """
            ).fetchall()

    first_rows = read_rows(first_path)
    assert first_rows == read_rows(second_path)
    assert len(first_rows) == 40
    assert first_rows[4] == (5, "A", None, 0)
    assert first_rows[32] == (33, "B", 1702.5, None)


def test_invalid_generated_database_is_not_published(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.sqlite3"

    def generate_invalid_database(temporary_path: Path) -> None:
        temporary_path.write_bytes(b"not sqlite")

    with pytest.raises(ValueError, match="invalid"):
        ensure_demo_database(database_path, generator=generate_invalid_database)

    assert not database_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_existing_database_without_demo_schema_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "empty.sqlite3"
    with sqlite3.connect(database_path):
        pass

    with pytest.raises(ValueError, match="configured SQLite database"):
        ensure_demo_database(database_path)
