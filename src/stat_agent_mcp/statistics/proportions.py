"""Two-proportion z-test and risk-difference calculation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from statsmodels.stats.proportion import proportions_ztest  # type: ignore[import-untyped]

from stat_agent_mcp.errors import DegenerateDataError, InsufficientObservationsError
from stat_agent_mcp.statistics.validation import PreparedProportionCounts


@dataclass(frozen=True, slots=True)
class ProportionGroupCalculation:
    """Success count and observed proportion for one independent group."""

    successes: int
    sample_size: int
    proportion: float

    @property
    def failures(self) -> int:
        """Return observed non-successes in the group."""
        return self.sample_size - self.successes


@dataclass(frozen=True, slots=True)
class ProportionCalculation:
    """Library-computed z-test result and group-ordered risk difference."""

    statistic: float
    p_value: float
    risk_difference: float
    group_1: ProportionGroupCalculation
    group_2: ProportionGroupCalculation


def run_two_proportion_z_test(counts: PreparedProportionCounts) -> ProportionCalculation:
    """Compute a two-sided pooled z-test after conservative approximation checks."""
    group_1 = _summarize(counts.successes[0], counts.totals[0])
    group_2 = _summarize(counts.successes[1], counts.totals[1])
    if any(
        value < 5
        for value in (
            group_1.successes,
            group_1.failures,
            group_2.successes,
            group_2.failures,
        )
    ):
        raise InsufficientObservationsError

    statistic_value, p_value_value = proportions_ztest(
        list(counts.successes),
        list(counts.totals),
        alternative="two-sided",
    )
    statistic = float(statistic_value)
    p_value = float(p_value_value)
    risk_difference = group_1.proportion - group_2.proportion
    if not all(math.isfinite(value) for value in (statistic, p_value, risk_difference)):
        raise DegenerateDataError
    return ProportionCalculation(
        statistic=statistic,
        p_value=p_value,
        risk_difference=risk_difference,
        group_1=group_1,
        group_2=group_2,
    )


def _summarize(successes: int, sample_size: int) -> ProportionGroupCalculation:
    if sample_size <= 0 or successes < 0 or successes > sample_size:
        raise InsufficientObservationsError
    return ProportionGroupCalculation(
        successes=successes,
        sample_size=sample_size,
        proportion=successes / sample_size,
    )
