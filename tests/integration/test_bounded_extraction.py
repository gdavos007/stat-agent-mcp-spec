"""Integration tests for deterministic bounded SQLite extraction."""

from pathlib import Path

import pytest

from stat_agent_mcp.connectors.base import BoundedExtractionRequest
from stat_agent_mcp.connectors.identifiers import validate_identifier
from stat_agent_mcp.connectors.sqlite import SQLiteConnector
from stat_agent_mcp.errors import ExtractionLimitError, MissingColumnError


def request(*columns: str, limit: int, hard_limit: int = 100) -> BoundedExtractionRequest:
    return BoundedExtractionRequest(
        table=validate_identifier("experiment_results"),
        columns=tuple(validate_identifier(name) for name in columns),
        limit=limit,
        hard_limit=hard_limit,
    )


def test_extract_selects_only_requested_columns_in_stable_primary_key_order(
    demo_database_path: Path,
) -> None:
    connector = SQLiteConnector(demo_database_path)

    extraction = connector.extract(request("record_id", "variant", limit=5))

    assert list(extraction.frame.columns) == ["record_id", "variant"]
    assert extraction.frame.to_dict(orient="records") == [
        {"record_id": 1, "variant": "A"},
        {"record_id": 2, "variant": "A"},
        {"record_id": 3, "variant": "A"},
        {"record_id": 4, "variant": "A"},
        {"record_id": 5, "variant": "A"},
    ]
    assert extraction.metadata.rows_examined == 5
    assert extraction.metadata.truncated is True
    assert extraction.metadata.order_columns == ("record_id",)
    assert extraction.metadata.sampled is False
    assert extraction.metadata.sampling_method == "none"


def test_extract_reports_when_full_table_fits_within_limit(demo_database_path: Path) -> None:
    connector = SQLiteConnector(demo_database_path)

    extraction = connector.extract(request("record_id", limit=50))

    assert len(extraction.frame) == 40
    assert extraction.metadata.rows_examined == 40
    assert extraction.metadata.truncated is False


def test_extract_enforces_hard_limit_defensively(demo_database_path: Path) -> None:
    connector = SQLiteConnector(demo_database_path)

    with pytest.raises(ExtractionLimitError):
        connector.extract(request("record_id", limit=11, hard_limit=10))


def test_extract_rejects_missing_columns(demo_database_path: Path) -> None:
    connector = SQLiteConnector(demo_database_path)

    with pytest.raises(MissingColumnError):
        connector.extract(request("missing_column", limit=5))
