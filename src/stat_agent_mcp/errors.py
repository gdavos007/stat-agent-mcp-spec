"""Typed domain errors that are safe to translate at the MCP boundary."""


class StatAgentError(Exception):
    """Base class for expected, non-secret-bearing domain failures."""

    code = "stat_agent_error"
    retryable = False


class ConnectionFailureError(StatAgentError):
    """Raised when the configured database cannot be accessed read-only."""

    code = "connection_failure"
    retryable = True

    def __init__(self) -> None:
        super().__init__("Unable to access the configured database.")


class UnsafeIdentifierError(StatAgentError):
    """Raised when an identifier violates the conservative lexical policy."""

    code = "unsafe_identifier"

    def __init__(self) -> None:
        super().__init__("An identifier contains unsupported or unsafe characters.")


class MissingTableError(StatAgentError):
    """Raised when a validated table does not exist."""

    code = "missing_table"

    def __init__(self) -> None:
        super().__init__("The requested table does not exist.")


class MissingColumnError(StatAgentError):
    """Raised when a validated column does not exist in the selected table."""

    code = "missing_column"

    def __init__(self) -> None:
        super().__init__("A requested column does not exist in the selected table.")


class DeterministicOrderingUnavailableError(StatAgentError):
    """Raised when bounded first-N extraction cannot establish a stable order."""

    code = "deterministic_ordering_unavailable"

    def __init__(self) -> None:
        super().__init__("The selected table does not provide a deterministic row order.")


class ExtractionLimitError(StatAgentError):
    """Raised when an extraction request violates its safety bounds."""

    code = "extraction_limit"

    def __init__(self) -> None:
        super().__init__("The requested extraction limit is invalid.")
