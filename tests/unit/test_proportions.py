"""Reference tests for the two-proportion z-test and risk difference."""

import pytest
from statsmodels.stats.proportion import proportions_ztest  # type: ignore[import-untyped]

from stat_agent_mcp.errors import InsufficientObservationsError
from stat_agent_mcp.statistics.proportions import run_two_proportion_z_test
from stat_agent_mcp.statistics.validation import ExclusionCounts, PreparedProportionCounts


def prepared(
    successes: tuple[int, int],
    totals: tuple[int, int],
) -> PreparedProportionCounts:
    return PreparedProportionCounts(
        successes=successes,
        totals=totals,
        exclusions=ExclusionCounts(
            null_rows_excluded=0,
            invalid_rows_excluded=0,
            unselected_group_rows_excluded=0,
            rows_included=sum(totals),
        ),
    )


def test_proportion_test_matches_statsmodels_and_risk_difference_reference() -> None:
    counts = prepared((12, 20), (30, 35))

    result = run_two_proportion_z_test(counts)
    statistic, p_value = proportions_ztest([12, 20], [30, 35], alternative="two-sided")

    assert result.statistic == pytest.approx(float(statistic), rel=1e-12)
    assert result.p_value == pytest.approx(float(p_value), rel=1e-12)
    assert result.risk_difference == pytest.approx((12 / 30) - (20 / 35), rel=1e-12)
    assert result.group_1.proportion == pytest.approx(0.4)
    assert result.group_2.proportion == pytest.approx(20 / 35)


def test_proportion_effect_direction_follows_group_order() -> None:
    forward = run_two_proportion_z_test(prepared((12, 20), (30, 35)))
    reverse = run_two_proportion_z_test(prepared((20, 12), (35, 30)))

    assert forward.risk_difference == pytest.approx(-reverse.risk_difference)
    assert forward.statistic == pytest.approx(-reverse.statistic)
    assert forward.p_value == pytest.approx(reverse.p_value)


@pytest.mark.parametrize(
    ("successes", "totals"),
    [((4, 10), (20, 20)), ((10, 10), (14, 20))],
)
def test_proportion_test_rejects_sparse_success_or_failure_counts(
    successes: tuple[int, int],
    totals: tuple[int, int],
) -> None:
    with pytest.raises(InsufficientObservationsError):
        run_two_proportion_z_test(prepared(successes, totals))
