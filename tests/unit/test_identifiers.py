"""Tests for conservative database identifier validation."""

import pytest

from stat_agent_mcp.connectors.identifiers import validate_identifier
from stat_agent_mcp.errors import UnsafeIdentifierError


@pytest.mark.parametrize("identifier", ["experiment_results", "record_id", "Table123"])
def test_validate_identifier_accepts_conservative_names(identifier: str) -> None:
    assert validate_identifier(identifier).value == identifier


@pytest.mark.parametrize(
    "identifier",
    ["", "has space", "table.column", 'bad"name', "users;DROP TABLE users", "éxample"],
)
def test_validate_identifier_rejects_unsafe_names_without_echoing_them(identifier: str) -> None:
    with pytest.raises(UnsafeIdentifierError) as caught:
        validate_identifier(identifier)

    if identifier:
        assert identifier not in str(caught.value)
