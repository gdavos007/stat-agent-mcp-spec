"""Tests for strict preparation of independent numeric samples."""

import pandas as pd
import pytest

from stat_agent_mcp.errors import (
    InsufficientObservationsError,
    InvalidBinaryOutcomeError,
    InvalidGroupValuesError,
    InvalidOutcomeValueError,
    InvalidSuccessValueError,
)
from stat_agent_mcp.statistics.validation import (
    prepare_independent_samples,
    prepare_proportion_counts,
)


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


def test_prepare_proportions_counts_successes_nulls_and_unselected_groups() -> None:
    frame = pd.DataFrame(
        {
            "outcome": [1, 0, None, 1, 0, 1, 0, "ignored-category"],
            "group": ["A", "A", "A", "B", "B", "B", "C", "C"],
        }
    )

    prepared = prepare_proportion_counts(frame, "outcome", "group", ("A", "B"), 1)

    assert prepared.successes == (1, 2)
    assert prepared.totals == (2, 3)
    assert prepared.exclusions.null_rows_excluded == 1
    assert prepared.exclusions.unselected_group_rows_excluded == 2
    assert prepared.exclusions.rows_included == 5


def test_prepare_proportions_requires_binary_selected_outcome() -> None:
    frame = pd.DataFrame(
        {
            "outcome": [0, 1, 2, 0, 1, 2],
            "group": ["A", "A", "A", "B", "B", "B"],
        }
    )

    with pytest.raises(InvalidBinaryOutcomeError):
        prepare_proportion_counts(frame, "outcome", "group", ("A", "B"), 1)


def test_prepare_proportions_requires_explicit_matching_success_value() -> None:
    frame = pd.DataFrame({"outcome": [0, 1, 0, 1], "group": ["A", "A", "B", "B"]})

    with pytest.raises(InvalidSuccessValueError):
        prepare_proportion_counts(frame, "outcome", "group", ("A", "B"), 2)
    with pytest.raises(InvalidSuccessValueError):
        prepare_proportion_counts(frame, "outcome", "group", ("A", "B"), True)
