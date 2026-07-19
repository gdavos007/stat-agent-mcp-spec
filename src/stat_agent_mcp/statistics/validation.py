"""Strict pandas validation and preparation for approved statistical tests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Integral, Real
from typing import TypeAlias

import pandas as pd

from stat_agent_mcp.errors import (
    InsufficientObservationsError,
    InvalidGroupValuesError,
    InvalidOutcomeValueError,
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
        return (float, normalized_float)
    if isinstance(value, str):
        return (str, value)
    raise InvalidGroupValuesError
