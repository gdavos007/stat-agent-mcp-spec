"""Reference tests for Welch's t-test and Hedges' g."""

import pandas as pd
import pytest
from scipy import stats  # type: ignore[import-untyped]

from stat_agent_mcp.errors import DegenerateDataError
from stat_agent_mcp.statistics.validation import ExclusionCounts, PreparedIndependentSamples
from stat_agent_mcp.statistics.welch import run_welch_t_test


def prepared(group_1: list[float], group_2: list[float]) -> PreparedIndependentSamples:
    return PreparedIndependentSamples(
        group_1=pd.Series(group_1, dtype="float64"),
        group_2=pd.Series(group_2, dtype="float64"),
        exclusions=ExclusionCounts(
            null_rows_excluded=0,
            invalid_rows_excluded=0,
            unselected_group_rows_excluded=0,
            rows_included=len(group_1) + len(group_2),
        ),
    )


def test_welch_matches_scipy_and_trusted_hedges_g_reference() -> None:
    samples = prepared([1.0, 2.0, 3.0, 4.0], [4.0, 5.0, 6.0, 7.0])

    result = run_welch_t_test(samples)
    reference = stats.ttest_ind(
        samples.group_1,
        samples.group_2,
        equal_var=False,
        alternative="two-sided",
    )

    assert result.statistic == pytest.approx(float(reference.statistic), rel=1e-12)
    assert result.p_value == pytest.approx(float(reference.pvalue), rel=1e-12)
    assert result.hedges_g == pytest.approx(-2.0206869632386524, rel=1e-12)
    assert result.group_1.mean == pytest.approx(2.5)
    assert result.group_2.mean == pytest.approx(5.5)


def test_welch_effect_direction_follows_group_order() -> None:
    forward = run_welch_t_test(prepared([1.0, 2.0, 3.0], [5.0, 6.0, 7.0]))
    reverse = run_welch_t_test(prepared([5.0, 6.0, 7.0], [1.0, 2.0, 3.0]))

    assert forward.hedges_g == pytest.approx(-reverse.hedges_g)
    assert forward.statistic == pytest.approx(-reverse.statistic)
    assert forward.p_value == pytest.approx(reverse.p_value)


def test_welch_rejects_zero_pooled_variance() -> None:
    with pytest.raises(DegenerateDataError):
        run_welch_t_test(prepared([1.0, 1.0], [1.0, 1.0]))
