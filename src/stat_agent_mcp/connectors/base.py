"""Database-independent connector contracts."""

from dataclasses import dataclass
from typing import Literal, Protocol

import pandas as pd

from stat_agent_mcp.connectors.identifiers import ValidatedIdentifier


@dataclass(frozen=True, slots=True)
class TableMetadata:
    """Safe metadata describing one discoverable relation."""

    name: str
    table_type: Literal["table", "view"]


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    """Database metadata needed to validate and profile one column."""

    name: str
    database_type: str
    nullable: bool
    primary_key_position: int | None


@dataclass(frozen=True, slots=True)
class TableDescription:
    """Resolved table metadata including its deterministic ordering strategy."""

    name: str
    table_type: Literal["table", "view"]
    columns: tuple[ColumnMetadata, ...]
    order_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoundedExtractionRequest:
    """Connector request for selected columns under an enforced hard limit."""

    table: ValidatedIdentifier
    columns: tuple[ValidatedIdentifier, ...]
    limit: int
    hard_limit: int
    requested_limit: int | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ExtractionMetadata:
    """Auditable metadata for a deterministic bounded extraction."""

    requested_limit: int
    effective_limit: int
    hard_limit: int
    rows_examined: int
    truncated: bool
    sampled: bool
    sampling_method: Literal["none"]
    random_seed: None
    order_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BoundedExtraction:
    """A bounded pandas frame and the metadata describing its extraction."""

    frame: pd.DataFrame
    metadata: ExtractionMetadata


class TableDiscoveryConnector(Protocol):
    """Narrow connector capability required by list_tables."""

    def list_tables(self) -> tuple[TableMetadata, ...]:
        """Return safe metadata for discoverable tables and views."""
        ...


class DatabaseConnector(TableDiscoveryConnector, Protocol):
    """Database capabilities required by the completed MVP slices."""

    def describe_table(self, table: ValidatedIdentifier) -> TableDescription:
        """Resolve safe column metadata and deterministic ordering."""
        ...

    def extract(self, request: BoundedExtractionRequest) -> BoundedExtraction:
        """Return only requested columns under the supplied hard limit."""
        ...
