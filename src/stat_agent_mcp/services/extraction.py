"""Identifier resolution and hard-bounded extraction orchestration."""

from stat_agent_mcp.connectors.base import (
    BoundedExtraction,
    BoundedExtractionRequest,
    DatabaseConnector,
    TableDescription,
)
from stat_agent_mcp.connectors.identifiers import validate_identifier
from stat_agent_mcp.errors import ExtractionLimitError, MissingColumnError


class ExtractionService:
    """Resolve metadata and enforce configured limits before connector extraction."""

    def __init__(self, connector: DatabaseConnector, default_limit: int, hard_limit: int) -> None:
        self._connector = connector
        self._default_limit = default_limit
        self._hard_limit = hard_limit

    def describe_table(self, table: str) -> TableDescription:
        """Validate and resolve a table through the connector metadata boundary."""
        return self._connector.describe_table(validate_identifier(table))

    def extract_from_description(
        self,
        description: TableDescription,
        columns: tuple[str, ...],
        max_rows: int | None,
    ) -> BoundedExtraction:
        """Extract resolved columns while clamping to the configured hard cap."""
        requested_limit = self._default_limit if max_rows is None else max_rows
        if requested_limit <= 0:
            raise ExtractionLimitError
        effective_limit = min(requested_limit, self._hard_limit)

        available_columns = {column.name for column in description.columns}
        validated_columns = tuple(validate_identifier(column) for column in columns)
        if not validated_columns or any(
            column.value not in available_columns for column in validated_columns
        ):
            raise MissingColumnError

        return self._connector.extract(
            BoundedExtractionRequest(
                table=validate_identifier(description.name),
                columns=validated_columns,
                limit=effective_limit,
                hard_limit=self._hard_limit,
                requested_limit=requested_limit,
            )
        )
