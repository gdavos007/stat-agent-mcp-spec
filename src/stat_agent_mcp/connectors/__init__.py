"""Database connector public interfaces and implementations."""

from stat_agent_mcp.connectors.base import (
    BoundedExtraction,
    BoundedExtractionRequest,
    ColumnMetadata,
    DatabaseConnector,
    ExtractionMetadata,
    TableDescription,
    TableDiscoveryConnector,
    TableMetadata,
)
from stat_agent_mcp.connectors.identifiers import ValidatedIdentifier, validate_identifier
from stat_agent_mcp.connectors.sqlite import SQLiteConnector

__all__ = [
    "BoundedExtraction",
    "BoundedExtractionRequest",
    "ColumnMetadata",
    "DatabaseConnector",
    "ExtractionMetadata",
    "SQLiteConnector",
    "TableDescription",
    "TableDiscoveryConnector",
    "TableMetadata",
    "ValidatedIdentifier",
    "validate_identifier",
]
