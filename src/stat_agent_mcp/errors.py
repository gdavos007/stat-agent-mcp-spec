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

