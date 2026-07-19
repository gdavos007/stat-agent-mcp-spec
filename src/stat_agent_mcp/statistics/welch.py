"""Welch's t-test and standardized effect-size calculation."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd
from scipy import stats  # type: ignore[import-untyped]
from statsmodels.stats.meta_analysis import effectsize_smd  # type: ignore[import-untyped]

from stat_agent_mcp.errors import DegenerateDataError
from stat_agent_mcp.statistics.validation import PreparedIndependentSamples


@dataclass(frozen=True, slots=True)
class NumericSampleCalculation:
    """Descriptive values for one validated independent sample."""

    sample_size: int
    mean: float
    standard_deviation: float


@dataclass(frozen=True, slots=True)
class WelchCalculation:
    """Library-computed Welch result and bias-corrected Hedges' g."""

    statistic: float
    p_value: float
    hedges_g: float
    group_1: NumericSampleCalculation
    group_2: NumericSampleCalculation


def run_welch_t_test(samples: PreparedIndependentSamples) -> WelchCalculation:
    """Compute a two-sided unequal-variance t-test and bias-corrected Hedges' g."""
    group_1 = _summarize(samples.group_1)
    group_2 = _summarize(samples.group_2)
    pooled_variance_numerator = (group_1.sample_size - 1) * group_1.standard_deviation**2 + (
        group_2.sample_size - 1
    ) * group_2.standard_deviation**2
    if pooled_variance_numerator <= 0.0:
        raise DegenerateDataError

    test_result = stats.ttest_ind(
        samples.group_1,
        samples.group_2,
        equal_var=False,
        nan_policy="raise",
        alternative="two-sided",
    )
    statistic = float(test_result.statistic)
    p_value = float(test_result.pvalue)
    hedges_g, _ = effectsize_smd(
        group_1.mean,
        group_1.standard_deviation,
        group_1.sample_size,
        group_2.mean,
        group_2.standard_deviation,
        group_2.sample_size,
    )
    effect_size = float(hedges_g)
    if not all(math.isfinite(value) for value in (statistic, p_value, effect_size)):
        raise DegenerateDataError

    return WelchCalculation(
        statistic=statistic,
        p_value=p_value,
        hedges_g=effect_size,
        group_1=group_1,
        group_2=group_2,
    )


def _summarize(series: pd.Series) -> NumericSampleCalculation:
    sample_size = len(series)
    mean = float(series.mean())
    standard_deviation = float(series.std(ddof=1))
    return NumericSampleCalculation(
        sample_size=sample_size,
        mean=mean,
        standard_deviation=standard_deviation,
    )
