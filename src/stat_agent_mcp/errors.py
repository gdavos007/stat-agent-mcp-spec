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


class IncompatibleColumnTypeError(StatAgentError):
    """Raised when a selected outcome has an incompatible declared or observed type."""

    code = "incompatible_column_type"

    def __init__(self) -> None:
        super().__init__("A selected column has an incompatible data type for this test.")


class InvalidGroupValuesError(StatAgentError):
    """Raised when exactly two distinct, populated groups were not provided."""

    code = "invalid_group_values"

    def __init__(self) -> None:
        super().__init__("Exactly two distinct group values with observations are required.")


class InvalidOutcomeValueError(StatAgentError):
    """Raised when a non-null outcome value is not finite numeric data."""

    code = "invalid_outcome_value"

    def __init__(self) -> None:
        super().__init__("The outcome contains a non-null value that is not finite numeric data.")


class InsufficientObservationsError(StatAgentError):
    """Raised when a statistical group has too few usable observations."""

    code = "insufficient_observations"

    def __init__(self) -> None:
        super().__init__("Each group requires at least two usable observations.")


class DegenerateDataError(StatAgentError):
    """Raised when the selected samples cannot produce a meaningful statistic."""

    code = "degenerate_data"

    def __init__(self) -> None:
        super().__init__("The selected samples have insufficient variation for this test.")


class UnsupportedTestError(StatAgentError):
    """Raised when a requested statistical test is not implemented in the current slice."""

    code = "unsupported_test"

    def __init__(self) -> None:
        super().__init__("The requested statistical test is not supported.")
