"""Orchestration for validated, bounded statistical testing."""

from typing import Final

from stat_agent_mcp.connectors.base import ExtractionMetadata
from stat_agent_mcp.errors import IncompatibleColumnTypeError, MissingColumnError
from stat_agent_mcp.models.common import ExtractionInfo
from stat_agent_mcp.models.statistical_tests import (
    NumericGroupSummary,
    ProportionGroupSummary,
    TwoProportionTestInput,
    TwoProportionTestResult,
    WelchTestInput,
    WelchTestResult,
)
from stat_agent_mcp.services.extraction import ExtractionService
from stat_agent_mcp.statistics.proportions import run_two_proportion_z_test
from stat_agent_mcp.statistics.validation import (
    prepare_independent_samples,
    prepare_proportion_counts,
)
from stat_agent_mcp.statistics.welch import run_welch_t_test

_NUMERIC_DATABASE_TYPES: Final = ("INT", "REAL", "FLOA", "DOUB", "NUM", "DEC")


class TestingService:
    """Coordinate safe extraction, validation, and approved statistical functions."""

    def __init__(self, extraction_service: ExtractionService) -> None:
        self._extraction_service = extraction_service

    def run_welch(self, request: WelchTestInput) -> WelchTestResult:
        """Run the MVP Welch test against explicitly selected columns and groups."""
        description = self._extraction_service.describe_table(request.table)
        columns = {column.name: column for column in description.columns}
        outcome_metadata = columns.get(request.outcome_column)
        if outcome_metadata is None or request.grouping_column not in columns:
            raise MissingColumnError
        if not any(
            token in outcome_metadata.database_type.upper() for token in _NUMERIC_DATABASE_TYPES
        ):
            raise IncompatibleColumnTypeError

        extraction = self._extraction_service.extract_from_description(
            description,
            (request.outcome_column, request.grouping_column),
            request.max_rows,
        )
        prepared = prepare_independent_samples(
            extraction.frame,
            request.outcome_column,
            request.grouping_column,
            request.group_values,
        )
        calculation = run_welch_t_test(prepared)
        metadata = extraction.metadata
        warnings = self._bounded_extraction_warnings(metadata.truncated)
        if min(len(prepared.group_1), len(prepared.group_2)) < 30:
            warnings.append(
                "At least one group has fewer than 30 observations; distribution shape "
                "and outliers require particular attention."
            )

        return WelchTestResult(
            null_hypothesis="The two population means are equal.",
            alternative_hypothesis="The two population means differ.",
            alpha=request.alpha,
            statistic=calculation.statistic,
            p_value=calculation.p_value,
            significant=calculation.p_value < request.alpha,
            group_summaries=(
                NumericGroupSummary(
                    group_value=request.group_values[0],
                    sample_size=calculation.group_1.sample_size,
                    mean=calculation.group_1.mean,
                    standard_deviation=calculation.group_1.standard_deviation,
                ),
                NumericGroupSummary(
                    group_value=request.group_values[1],
                    sample_size=calculation.group_2.sample_size,
                    mean=calculation.group_2.mean,
                    standard_deviation=calculation.group_2.standard_deviation,
                ),
            ),
            effect_size=calculation.hedges_g,
            effect_size_direction="group_1 minus group_2",
            assumptions=(
                "Observations are independent within and between groups.",
                "The outcome is continuous numeric data.",
                "Each group is approximately normal or sufficiently large for robust inference.",
                "Extreme outliers do not dominate either sample.",
                "Statistical significance does not establish causality or business importance.",
            ),
            warnings=tuple(warnings),
            rows_examined=metadata.rows_examined,
            rows_included=prepared.exclusions.rows_included,
            null_rows_excluded=prepared.exclusions.null_rows_excluded,
            invalid_rows_excluded=prepared.exclusions.invalid_rows_excluded,
            unselected_group_rows_excluded=(prepared.exclusions.unselected_group_rows_excluded),
            extraction=self._extraction_info(metadata),
        )

    def run_two_proportion(
        self,
        request: TwoProportionTestInput,
    ) -> TwoProportionTestResult:
        """Run the MVP two-proportion z-test with explicit success semantics."""
        description = self._extraction_service.describe_table(request.table)
        columns = {column.name for column in description.columns}
        if request.outcome_column not in columns or request.grouping_column not in columns:
            raise MissingColumnError
        extraction = self._extraction_service.extract_from_description(
            description,
            (request.outcome_column, request.grouping_column),
            request.max_rows,
        )
        prepared = prepare_proportion_counts(
            extraction.frame,
            request.outcome_column,
            request.grouping_column,
            request.group_values,
            request.success_value,
        )
        calculation = run_two_proportion_z_test(prepared)
        metadata = extraction.metadata
        warnings = self._bounded_extraction_warnings(metadata.truncated)
        approximation_counts = (
            calculation.group_1.successes,
            calculation.group_1.failures,
            calculation.group_2.successes,
            calculation.group_2.failures,
        )
        if any(5 <= count <= 9 for count in approximation_counts):
            warnings.append(
                "The normal approximation is borderline because a success or failure count "
                "is between 5 and 9."
            )

        return TwoProportionTestResult(
            null_hypothesis="The two population success proportions are equal.",
            alternative_hypothesis="The two population success proportions differ.",
            success_value=request.success_value,
            alpha=request.alpha,
            statistic=calculation.statistic,
            p_value=calculation.p_value,
            significant=calculation.p_value < request.alpha,
            group_summaries=(
                ProportionGroupSummary(
                    group_value=request.group_values[0],
                    successes=calculation.group_1.successes,
                    sample_size=calculation.group_1.sample_size,
                    proportion=calculation.group_1.proportion,
                ),
                ProportionGroupSummary(
                    group_value=request.group_values[1],
                    successes=calculation.group_2.successes,
                    sample_size=calculation.group_2.sample_size,
                    proportion=calculation.group_2.proportion,
                ),
            ),
            effect_size=calculation.risk_difference,
            effect_size_direction="group_1 proportion minus group_2 proportion",
            assumptions=(
                "Observations are independent within and between groups.",
                "The outcome has exactly two non-null values in the selected groups.",
                "The caller explicitly identified which outcome value represents success.",
                "Each group has at least five observed successes and five observed failures.",
                "Statistical significance does not establish causality or business importance.",
            ),
            warnings=tuple(warnings),
            rows_examined=metadata.rows_examined,
            rows_included=prepared.exclusions.rows_included,
            null_rows_excluded=prepared.exclusions.null_rows_excluded,
            invalid_rows_excluded=prepared.exclusions.invalid_rows_excluded,
            unselected_group_rows_excluded=(prepared.exclusions.unselected_group_rows_excluded),
            extraction=self._extraction_info(metadata),
        )

    @staticmethod
    def _bounded_extraction_warnings(truncated: bool) -> list[str]:
        if not truncated:
            return []
        return [
            "The result uses a deterministic first-N extract and may not represent the full table."
        ]

    @staticmethod
    def _extraction_info(metadata: ExtractionMetadata) -> ExtractionInfo:
        return ExtractionInfo(
            requested_limit=metadata.requested_limit,
            effective_limit=metadata.effective_limit,
            hard_limit=metadata.hard_limit,
            rows_examined=metadata.rows_examined,
            truncated=metadata.truncated,
            sampled=metadata.sampled,
            sampling_method=metadata.sampling_method,
            random_seed=metadata.random_seed,
            order_columns=metadata.order_columns,
        )
