"""Create the deterministic SQLite database used by the demo and tests."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def create_demo_database(database_path: Path) -> None:
    """Create a new deterministic experiment database without overwriting files."""
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


def main() -> None:
    """Parse the output path and create the demonstration database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database_path", type=Path)
    arguments = parser.parse_args()
    create_demo_database(arguments.database_path)


if __name__ == "__main__":
    main()
