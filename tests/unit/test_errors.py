"""Tests for domain errors and their safe public details."""

from stat_agent_mcp.errors import ConnectionFailureError


def test_connection_error_does_not_contain_database_path() -> None:
    sensitive_path = "/private/customer/database.sqlite3"

    error = ConnectionFailureError()

    assert sensitive_path not in str(error)
    assert error.code == "connection_failure"
    assert error.retryable is True
