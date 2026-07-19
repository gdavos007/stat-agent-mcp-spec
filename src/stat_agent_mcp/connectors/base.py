"""Database-independent connector contracts."""

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class TableMetadata:
    """Safe metadata describing one discoverable relation."""

    name: str
    table_type: Literal["table", "view"]


class DatabaseConnector(Protocol):
    """Database capabilities required by the completed MVP slices."""

    def list_tables(self) -> tuple[TableMetadata, ...]:
        """Return safe metadata for discoverable tables and views."""
        ...

