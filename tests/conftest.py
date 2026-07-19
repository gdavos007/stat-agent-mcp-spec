"""Shared deterministic fixtures for integration tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from scripts.create_demo_db import create_demo_database


@pytest.fixture
def demo_database_path(tmp_path: Path) -> Iterator[Path]:
    """Create a fresh deterministic SQLite demonstration database."""
    database_path = tmp_path / "demo.sqlite3"
    create_demo_database(database_path)
    yield database_path

