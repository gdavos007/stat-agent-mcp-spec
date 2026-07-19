"""Deterministic rule-based profiling of bounded pandas data."""

from __future__ import annotations

import math
from datetime import date, datetime
from numbers import Integral, Real
from typing import Final

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype

from stat_agent_mcp.connectors.base import ColumnMetadata
from stat_agent_mcp.models.common import ExtractionInfo
from stat_agent_mcp.models.profiles import (
    ColumnProfile,
    NumericSummary,
    ProfileValue,
    SuggestedRole,
    TableProfileData,
    ValueFrequency,
)
from stat_agent_mcp.services.extraction import ExtractionService

_SENSITIVE_NAME_PARTS: Final = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "ssn",
)
_NUMERIC_DATABASE_TYPES: Final = ("INT", "REAL", "FLOA", "DOUB", "NUM", "DEC")
_DATETIME_DATABASE_TYPES: Final = ("DATE", "TIME")
_MAX_EXAMPLES: Final = 3
_MAX_TOP_VALUES: Final = 5
_MAX_VALUE_LENGTH: Final = 64


class ProfilingService:
    """Coordinate metadata, bounded extraction, and deterministic column profiles."""

    def __init__(self, extraction_service: ExtractionService) -> None:
        self._extraction_service = extraction_service

    def profile(self, table: str, max_rows: int | None) -> TableProfileData:
        """Profile all columns in a resolved table using one bounded extraction."""
        description = self._extraction_service.describe_table(table)
        extraction = self._extraction_service.extract_from_description(
            description,
            tuple(column.name for column in description.columns),
            max_rows,
        )
        column_profiles = tuple(
            profile_column(column, extraction.frame[column.name]) for column in description.columns
        )
        metadata = extraction.metadata
        return TableProfileData(
            table_name=description.name,
            row_count_considered=metadata.rows_examined,
            columns=column_profiles,
            extraction=ExtractionInfo(
                requested_limit=metadata.requested_limit,
                effective_limit=metadata.effective_limit,
                hard_limit=metadata.hard_limit,
                rows_examined=metadata.rows_examined,
                truncated=metadata.truncated,
                sampled=metadata.sampled,
                sampling_method=metadata.sampling_method,
                random_seed=metadata.random_seed,
                order_columns=metadata.order_columns,
            ),
        )


def profile_column(metadata: ColumnMetadata, series: pd.Series) -> ColumnProfile:
    """Build a deterministic profile using documented cardinality and type heuristics."""
    row_count = len(series)
    non_null = series.dropna()
    non_null_count = len(non_null)
    null_count = row_count - non_null_count
    unique_count = int(non_null.nunique(dropna=True))
    suggested_role = _suggest_role(metadata, series, non_null, unique_count)
    sensitive = _is_sensitive_name(metadata.name)
    suppress_values = sensitive or suggested_role is SuggestedRole.IDENTIFIER

    return ColumnProfile(
        name=metadata.name,
        database_type=metadata.database_type,
        pandas_type=str(series.dtype),
        suggested_role=suggested_role,
        row_count_considered=row_count,
        non_null_count=non_null_count,
        null_count=null_count,
        null_percentage=(null_count / row_count * 100.0) if row_count else 0.0,
        unique_count=unique_count,
        example_values=() if suppress_values else _example_values(non_null),
        numeric_summary=_numeric_summary(metadata, series, non_null),
        top_values=()
        if suppress_values
        else _top_values(non_null, unique_count, _is_numeric(metadata, series)),
    )


def _suggest_role(
    metadata: ColumnMetadata,
    series: pd.Series,
    non_null: pd.Series,
    unique_count: int,
) -> SuggestedRole:
    if _is_datetime(metadata, series):
        return SuggestedRole.DATETIME
    if metadata.primary_key_position is not None or _looks_like_identifier(
        metadata.name, len(non_null), unique_count
    ):
        return SuggestedRole.IDENTIFIER
    if not len(non_null):
        return SuggestedRole.OTHER
    if unique_count == 2 and (_is_numeric(metadata, series) or is_bool_dtype(series.dtype)):
        return SuggestedRole.BINARY_OUTCOME
    if _is_numeric(metadata, series) and unique_count >= 10:
        return SuggestedRole.CONTINUOUS_OUTCOME
    if 2 <= unique_count <= 20:
        return SuggestedRole.GROUPING_VARIABLE
    return SuggestedRole.OTHER


def _looks_like_identifier(name: str, non_null_count: int, unique_count: int) -> bool:
    normalized = name.casefold()
    name_hint = normalized == "id" or normalized.endswith("_id") or "identifier" in normalized
    return name_hint and non_null_count >= 10 and unique_count / non_null_count >= 0.95


def _is_numeric(metadata: ColumnMetadata, series: pd.Series) -> bool:
    declared_type = metadata.database_type.upper()
    return is_numeric_dtype(series.dtype) or any(
        token in declared_type for token in _NUMERIC_DATABASE_TYPES
    )


def _is_datetime(metadata: ColumnMetadata, series: pd.Series) -> bool:
    declared_type = metadata.database_type.upper()
    return is_datetime64_any_dtype(series.dtype) or any(
        token in declared_type for token in _DATETIME_DATABASE_TYPES
    )


def _is_sensitive_name(name: str) -> bool:
    normalized = name.casefold()
    return any(part in normalized for part in _SENSITIVE_NAME_PARTS)


def _example_values(non_null: pd.Series) -> tuple[ProfileValue, ...]:
    examples: list[ProfileValue] = []
    seen: set[tuple[str, str]] = set()
    for value in non_null:
        safe_value = _safe_value(value)
        key = (type(safe_value).__name__, repr(safe_value))
        if key not in seen:
            examples.append(safe_value)
            seen.add(key)
        if len(examples) == _MAX_EXAMPLES:
            break
    return tuple(examples)


def _top_values(
    non_null: pd.Series,
    unique_count: int,
    numeric: bool,
) -> tuple[ValueFrequency, ...]:
    if unique_count == 0 or (numeric and unique_count > 20):
        return ()
    counts: dict[tuple[str, str], tuple[ProfileValue, int]] = {}
    for value in non_null:
        safe_value = _safe_value(value)
        key = (type(safe_value).__name__, repr(safe_value))
        existing = counts.get(key)
        counts[key] = (safe_value, 1 if existing is None else existing[1] + 1)
    ordered = sorted(counts.values(), key=lambda item: (-item[1], repr(item[0])))
    return tuple(
        ValueFrequency(value=value, count=count) for value, count in ordered[:_MAX_TOP_VALUES]
    )


def _numeric_summary(
    metadata: ColumnMetadata,
    series: pd.Series,
    non_null: pd.Series,
) -> NumericSummary | None:
    if not _is_numeric(metadata, series) or non_null.empty:
        return None
    numeric_values = pd.to_numeric(non_null, errors="coerce")
    finite_values = [float(value) for value in numeric_values if math.isfinite(float(value))]
    if not finite_values:
        return None
    numeric_series = pd.Series(finite_values, dtype="float64")
    standard_deviation = float(numeric_series.std(ddof=1)) if len(numeric_series) > 1 else None
    return NumericSummary(
        minimum=float(numeric_series.min()),
        maximum=float(numeric_series.max()),
        mean=float(numeric_series.mean()),
        median=float(numeric_series.median()),
        standard_deviation=standard_deviation,
    )


def _safe_value(value: object) -> ProfileValue:
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        numeric_value = float(value)
        return numeric_value if math.isfinite(numeric_value) else str(numeric_value)
    text = value.isoformat() if isinstance(value, (date, datetime)) else str(value)
    return text[:_MAX_VALUE_LENGTH]
