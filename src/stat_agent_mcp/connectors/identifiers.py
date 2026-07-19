"""Conservative lexical validation for database identifiers."""

import re
from dataclasses import dataclass
from typing import Final

from stat_agent_mcp.errors import UnsafeIdentifierError

_SAFE_IDENTIFIER: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ValidatedIdentifier:
    """An identifier that passed the database-independent lexical policy."""

    value: str


def validate_identifier(identifier: str) -> ValidatedIdentifier:
    """Return a validated identifier or raise without echoing unsafe input."""
    if not _SAFE_IDENTIFIER.fullmatch(identifier):
        raise UnsafeIdentifierError
    return ValidatedIdentifier(identifier)
