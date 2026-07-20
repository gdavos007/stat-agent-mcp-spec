"""Create the deterministic SQLite database used by the demo and tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from stat_agent_mcp.connectors.demo_sqlite import create_demo_database


def main() -> None:
    """Parse the output path and create the demonstration database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database_path", type=Path)
    arguments = parser.parse_args()
    create_demo_database(arguments.database_path)


if __name__ == "__main__":
    main()
