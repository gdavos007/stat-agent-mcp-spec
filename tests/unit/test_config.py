"""Tests for environment-backed configuration validation."""

from collections.abc import Mapping

import pytest
from pydantic import SecretStr, ValidationError

from stat_agent_mcp.config import Settings, load_settings

SENSITIVE_PATH = "/Users/example/private/customer-data.sqlite3"


def valid_environment(**overrides: str) -> Mapping[str, str]:
    environment = {
        "STAT_MCP_CONNECTION_NAME": "demo_sqlite",
        "STAT_MCP_SQLITE_PATH": SENSITIVE_PATH,
        "STAT_MCP_DEFAULT_ROW_LIMIT": "100",
        "STAT_MCP_HARD_ROW_LIMIT": "1000",
    }
    environment.update(overrides)
    return environment


def test_load_settings_separates_public_name_from_internal_path() -> None:
    settings = load_settings(valid_environment())

    assert settings.connection_name == "demo_sqlite"
    assert str(settings.sqlite_path()) == SENSITIVE_PATH
    assert SENSITIVE_PATH not in repr(settings)
    assert SENSITIVE_PATH not in settings.model_dump_json()


@pytest.mark.parametrize(
    ("environment_name", "value"),
    [
        ("STAT_MCP_DEFAULT_ROW_LIMIT", "0"),
        ("STAT_MCP_DEFAULT_ROW_LIMIT", "-1"),
        ("STAT_MCP_HARD_ROW_LIMIT", "0"),
        ("STAT_MCP_HARD_ROW_LIMIT", "-1"),
    ],
)
def test_row_limits_must_be_positive(environment_name: str, value: str) -> None:
    with pytest.raises(ValidationError) as caught:
        load_settings(valid_environment(**{environment_name: value}))

    assert SENSITIVE_PATH not in str(caught.value)


def test_default_limit_must_not_exceed_hard_limit() -> None:
    with pytest.raises(ValidationError, match="default row limit must not exceed hard row limit") as caught:
        load_settings(
            valid_environment(
                STAT_MCP_DEFAULT_ROW_LIMIT="1001",
                STAT_MCP_HARD_ROW_LIMIT="1000",
            )
        )

    assert SENSITIVE_PATH not in str(caught.value)


def test_missing_sqlite_path_names_variable_without_exposing_other_values() -> None:
    environment = dict(valid_environment())
    del environment["STAT_MCP_SQLITE_PATH"]

    with pytest.raises(ValueError, match="STAT_MCP_SQLITE_PATH") as caught:
        load_settings(environment)

    assert SENSITIVE_PATH not in str(caught.value)


def test_non_integer_limit_reports_only_the_environment_variable_name() -> None:
    invalid_value = "not-an-integer-secret"

    with pytest.raises(ValueError, match="STAT_MCP_DEFAULT_ROW_LIMIT") as caught:
        load_settings(valid_environment(STAT_MCP_DEFAULT_ROW_LIMIT=invalid_value))

    assert invalid_value not in str(caught.value)
    assert SENSITIVE_PATH not in str(caught.value)


def test_invalid_public_connection_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        load_settings(valid_environment(STAT_MCP_CONNECTION_NAME="unsafe name"))


def test_settings_are_immutable() -> None:
    settings = load_settings(valid_environment())

    with pytest.raises(ValidationError):
        settings.default_row_limit = 200


def test_settings_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Settings(
            connection_name="demo_sqlite",
            sqlite_path_secret=SecretStr(SENSITIVE_PATH),
            default_row_limit=100,
            hard_row_limit=1000,
            unexpected="value",  # type: ignore[call-arg]
        )
