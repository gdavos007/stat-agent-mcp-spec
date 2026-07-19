"""Tests for deterministic column profiling and role heuristics."""

import pandas as pd
import pytest

from stat_agent_mcp.connectors.base import ColumnMetadata
from stat_agent_mcp.models.profiles import SuggestedRole
from stat_agent_mcp.services.profiling import profile_column


def column(
    name: str,
    database_type: str,
    *,
    primary_key_position: int | None = None,
) -> ColumnMetadata:
    return ColumnMetadata(
        name=name,
        database_type=database_type,
        nullable=primary_key_position is None,
        primary_key_position=primary_key_position,
    )


def test_profile_column_classifies_demo_roles() -> None:
    identifier = profile_column(
        column("record_id", "INTEGER", primary_key_position=1),
        pd.Series(range(1, 21), name="record_id"),
    )
    grouping = profile_column(
        column("variant", "TEXT"),
        pd.Series(["B", "A", "A", "B"], name="variant"),
    )
    continuous = profile_column(
        column("account_balance", "REAL"),
        pd.Series([float(value) for value in range(20)], name="account_balance"),
    )
    binary = profile_column(
        column("converted", "INTEGER"),
        pd.Series([0, 1, 0, 1], name="converted"),
    )

    assert identifier.suggested_role is SuggestedRole.IDENTIFIER
    assert identifier.example_values == ()
    assert grouping.suggested_role is SuggestedRole.GROUPING_VARIABLE
    assert [(item.value, item.count) for item in grouping.top_values] == [("A", 2), ("B", 2)]
    assert continuous.suggested_role is SuggestedRole.CONTINUOUS_OUTCOME
    assert continuous.numeric_summary is not None
    assert continuous.numeric_summary.median == 9.5
    assert binary.suggested_role is SuggestedRole.BINARY_OUTCOME


def test_profile_column_counts_nulls_and_suppresses_sensitive_examples() -> None:
    profile = profile_column(
        column("api_token", "TEXT"),
        pd.Series(["top-secret", None, "another-secret"], name="api_token"),
    )

    assert profile.row_count_considered == 3
    assert profile.non_null_count == 2
    assert profile.null_count == 1
    assert profile.null_percentage == pytest.approx(100 / 3)
    assert profile.unique_count == 2
    assert profile.example_values == ()
    assert profile.top_values == ()


def test_profile_column_limits_and_deterministically_orders_categorical_values() -> None:
    profile = profile_column(
        column("segment", "TEXT"),
        pd.Series(["z", "b", "a", "z", "b", "z"], name="segment"),
    )

    assert profile.example_values == ("z", "b", "a")
    assert [(item.value, item.count) for item in profile.top_values] == [
        ("z", 3),
        ("b", 2),
        ("a", 1),
    ]
