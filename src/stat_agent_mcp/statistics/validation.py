"""Strict pandas validation and preparation for approved statistical tests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import TypeAlias

import pandas as pd

from stat_agent_mcp.errors import (
    InsufficientObservationsError,
    InvalidBinaryOutcomeError,
    InvalidGroupValuesError,
    InvalidOutcomeValueError,
    InvalidSuccessValueError,
)

Scalar: TypeAlias = str | int | float | bool
ScalarKey: TypeAlias = tuple[type[object], Scalar]


@dataclass(frozen=True, slots=True)
class ExclusionCounts:
    """Mutually exclusive row-accounting categories for a prepared test."""

    null_rows_excluded: int
    invalid_rows_excluded: int
    unselected_group_rows_excluded: int
    rows_included: int


@dataclass(frozen=True, slots=True)
class PreparedIndependentSamples:
    """Two finite independent numeric samples and their exclusion audit."""

    group_1: pd.Series
    group_2: pd.Series
    exclusions: ExclusionCounts


@dataclass(frozen=True, slots=True)
class PreparedProportionCounts:
    """Validated success and total counts for two independent groups."""

    successes: tuple[int, int]
    totals: tuple[int, int]
    exclusions: ExclusionCounts


def prepare_independent_samples(
    frame: pd.DataFrame,
    outcome_column: str,
    grouping_column: str,
    group_values: tuple[Scalar, ...],
) -> PreparedIndependentSamples:
    """Validate and prepare two groups without silently discarding invalid values."""
    if len(group_values) != 2:
        raise InvalidGroupValuesError
    group_1_value, group_2_value = group_values
    group_1_key = _scalar_key(group_1_value)
    group_2_key = _scalar_key(group_2_value)
    if group_1_key == group_2_key:
        raise InvalidGroupValuesError

    outcome = frame[outcome_column]
    grouping = frame[grouping_column]
    null_mask = outcome.isna() | grouping.isna()
    non_null_outcome = outcome.loc[~null_mask]
    non_null_grouping = grouping.loc[~null_mask]
    numeric_outcome = pd.to_numeric(non_null_outcome, errors="coerce")
    invalid_mask = numeric_outcome.isna() | ~numeric_outcome.map(
        lambda value: math.isfinite(float(value))
    )
    invalid_count = int(invalid_mask.sum())
    if invalid_count:
        raise InvalidOutcomeValueError

    group_keys = non_null_grouping.map(_scalar_key)
    group_1_mask = group_keys == group_1_key
    group_2_mask = group_keys == group_2_key
    selected_mask = group_1_mask | group_2_mask
    group_1 = numeric_outcome.loc[group_1_mask].astype("float64").reset_index(drop=True)
    group_2 = numeric_outcome.loc[group_2_mask].astype("float64").reset_index(drop=True)
    if len(group_1) < 2 or len(group_2) < 2:
        raise InsufficientObservationsError

    return PreparedIndependentSamples(
        group_1=group_1,
        group_2=group_2,
        exclusions=ExclusionCounts(
            null_rows_excluded=int(null_mask.sum()),
            invalid_rows_excluded=0,
            unselected_group_rows_excluded=int((~selected_mask).sum()),
            rows_included=len(group_1) + len(group_2),
        ),
    )


def prepare_proportion_counts(
    frame: pd.DataFrame,
    outcome_column: str,
    grouping_column: str,
    group_values: tuple[Scalar, ...],
    success_value: Scalar,
) -> PreparedProportionCounts:
    """Validate selected groups as binary and count the explicit success value."""
    if len(group_values) != 2:
        raise InvalidGroupValuesError
    group_1_key = _scalar_key(group_values[0])
    group_2_key = _scalar_key(group_values[1])
    if group_1_key == group_2_key:
        raise InvalidGroupValuesError

    outcome = frame[outcome_column]
    grouping = frame[grouping_column]
    null_mask = outcome.isna() | grouping.isna()
    non_null_outcome = outcome.loc[~null_mask]
    non_null_grouping = grouping.loc[~null_mask]
    group_keys = non_null_grouping.map(_scalar_key)
    group_1_mask = group_keys == group_1_key
    group_2_mask = group_keys == group_2_key
    selected_mask = group_1_mask | group_2_mask
    totals = (int(group_1_mask.sum()), int(group_2_mask.sum()))
    if 0 in totals:
        raise InvalidGroupValuesError

    try:
        group_1_outcomes = non_null_outcome.loc[group_1_mask].map(_scalar_key)
        group_2_outcomes = non_null_outcome.loc[group_2_mask].map(_scalar_key)
    except InvalidGroupValuesError:
        raise InvalidBinaryOutcomeError from None
    distinct_outcomes = set(group_1_outcomes) | set(group_2_outcomes)
    if len(distinct_outcomes) != 2:
        raise InvalidBinaryOutcomeError
    try:
        success_key = _scalar_key(success_value)
    except InvalidGroupValuesError:
        raise InvalidSuccessValueError from None
    if success_key not in distinct_outcomes:
        raise InvalidSuccessValueError

    successes = (
        int((group_1_outcomes == success_key).sum()),
        int((group_2_outcomes == success_key).sum()),
    )
    return PreparedProportionCounts(
        successes=successes,
        totals=totals,
        exclusions=ExclusionCounts(
            null_rows_excluded=int(null_mask.sum()),
            invalid_rows_excluded=0,
            unselected_group_rows_excluded=int((~selected_mask).sum()),
            rows_included=sum(totals),
        ),
    )


def _scalar_key(value: object) -> ScalarKey:
    if isinstance(value, bool):
        return (bool, value)
    if isinstance(value, Integral):
        normalized = int(value)
        return (int, normalized)
    if isinstance(value, Real):
        normalized_float = float(value)
        if not math.isfinite(normalized_float):
            raise InvalidGroupValuesError
        if normalized_float.is_integer():
            return (int, int(normalized_float))
        return (float, normalized_float)
    if isinstance(value, str):
        return (str, value)
    raise InvalidGroupValuesError
