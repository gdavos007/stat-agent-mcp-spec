"""Deterministic SQLite demo data creation and atomic startup bootstrap."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Callable
from pathlib import Path


def create_demo_database(database_path: Path) -> None:
    """Create the deterministic experiment database without overwriting a file."""
    if database_path.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {database_path.name}")

    rows: list[tuple[int, str, float | None, int | None]] = []
    for record_id in range(1, 41):
        variant = "A" if record_id <= 20 else "B"
        group_adjustment = 0.0 if variant == "A" else 125.0
        account_balance: float | None = 1_000.0 + (record_id * 17.5) + group_adjustment
        converted: int | None = int(record_id % (3 if variant == "A" else 2) == 0)
        if record_id in {5, 27}:
            account_balance = None
        if record_id in {8, 33}:
            converted = None
        rows.append((record_id, variant, account_balance, converted))

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE experiment_results (
                record_id INTEGER PRIMARY KEY,
                variant TEXT NOT NULL,
                account_balance REAL,
                converted INTEGER CHECK (converted IN (0, 1))
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO experiment_results (
                record_id,
                variant,
                account_balance,
                converted
            ) VALUES (?, ?, ?, ?)
            """,
            rows,
        )


def validate_demo_database(database_path: Path) -> None:
    """Require an intact SQLite database with the deterministic demo schema."""
    try:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as connection:
            integrity_result = connection.execute("PRAGMA integrity_check").fetchone()
            columns = connection.execute(
                "SELECT name, type, \"notnull\", pk FROM pragma_table_info('experiment_results')"
            ).fetchall()
            row_count = connection.execute("SELECT COUNT(*) FROM experiment_results").fetchone()
    except sqlite3.Error as error:
        raise ValueError("configured SQLite database is invalid") from error
    if integrity_result != ("ok",):
        raise ValueError("configured SQLite database failed its integrity check")
    if columns != [
        ("record_id", "INTEGER", 0, 1),
        ("variant", "TEXT", 1, 0),
        ("account_balance", "REAL", 0, 0),
        ("converted", "INTEGER", 0, 0),
    ] or row_count != (40,):
        raise ValueError("configured SQLite database does not contain the expected demo schema")


def ensure_demo_database(
    database_path: Path,
    *,
    generator: Callable[[Path], None] = create_demo_database,
) -> bool:
    """Atomically create absent demo data, or validate and reuse an existing database."""
    if database_path.exists():
        validate_demo_database(database_path)
        return False

    database_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{database_path.name}.",
        suffix=".tmp",
        dir=database_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    temporary_path.unlink()
    try:
        generator(temporary_path)
        validate_demo_database(temporary_path)
        os.replace(temporary_path, database_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True
