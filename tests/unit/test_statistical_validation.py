"""Tests for strict preparation of independent numeric samples."""

import pandas as pd
import pytest

from stat_agent_mcp.errors import (
    InsufficientObservationsError,
    InvalidGroupValuesError,
    InvalidOutcomeValueError,
)
from stat_agent_mcp.statistics.validation import prepare_independent_samples


def test_prepare_samples_counts_null_and_unselected_rows() -> None:
    frame = pd.DataFrame(
        {
            "outcome": [1.0, 2.0, None, 10.0, 3.0, 4.0],
            "group": ["A", "A", "A", "C", "B", "B"],
        }
    )

    prepared = prepare_independent_samples(frame, "outcome", "group", ("A", "B"))

    assert prepared.group_1.tolist() == [1.0, 2.0]
    assert prepared.group_2.tolist() == [3.0, 4.0]
    assert prepared.exclusions.null_rows_excluded == 1
    assert prepared.exclusions.invalid_rows_excluded == 0
    assert prepared.exclusions.unselected_group_rows_excluded == 1
    assert prepared.exclusions.rows_included == 4


def test_prepare_samples_rejects_non_null_invalid_numeric_values() -> None:
    frame = pd.DataFrame(
        {
            "outcome": [1.0, "bad-value", 3.0, 4.0],
            "group": ["A", "A", "B", "B"],
        }
    )

    with pytest.raises(InvalidOutcomeValueError):
        prepare_independent_samples(frame, "outcome", "group", ("A", "B"))


@pytest.mark.parametrize("group_values", [("A", "A"), ("A",), ("A", "B", "C")])
def test_prepare_samples_requires_exactly_two_distinct_groups(
    group_values: tuple[str, ...],
) -> None:
    frame = pd.DataFrame({"outcome": [1.0, 2.0], "group": ["A", "B"]})

    with pytest.raises(InvalidGroupValuesError):
        prepare_independent_samples(frame, "outcome", "group", group_values)


def test_prepare_samples_requires_two_observations_in_each_group() -> None:
    frame = pd.DataFrame({"outcome": [1.0, 2.0, 3.0], "group": ["A", "A", "B"]})

    with pytest.raises(InsufficientObservationsError):
        prepare_independent_samples(frame, "outcome", "group", ("A", "B"))
