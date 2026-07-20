"""Environment-backed configuration with secret-safe representations."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

CONNECTION_NAME_ENV = "STAT_MCP_CONNECTION_NAME"
SQLITE_PATH_ENV = "STAT_MCP_SQLITE_PATH"
DEFAULT_ROW_LIMIT_ENV = "STAT_MCP_DEFAULT_ROW_LIMIT"
HARD_ROW_LIMIT_ENV = "STAT_MCP_HARD_ROW_LIMIT"
HTTP_PORT_ENV = "PORT"
DEFAULT_HTTP_PORT = 8000


class Settings(BaseModel):
    """Validated server settings loaded from environment variables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connection_name: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    sqlite_path_secret: SecretStr = Field(repr=False)
    default_row_limit: int = Field(gt=0)
    hard_row_limit: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_row_limits(self) -> Self:
        """Require the normal extraction limit to fit within the hard safety cap."""
        if self.default_row_limit > self.hard_row_limit:
            raise ValueError("default row limit must not exceed hard row limit")
        return self

    def sqlite_path(self) -> Path:
        """Return the internal SQLite path without exposing it in model output."""
        return Path(self.sqlite_path_secret.get_secret_value())


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load settings from an environment mapping without retaining raw values."""
    source = os.environ if environ is None else environ
    return Settings(
        connection_name=source.get(CONNECTION_NAME_ENV, "demo_sqlite"),
        sqlite_path_secret=SecretStr(_required_value(source, SQLITE_PATH_ENV)),
        default_row_limit=_positive_integer(source, DEFAULT_ROW_LIMIT_ENV, default=1_000),
        hard_row_limit=_positive_integer(source, HARD_ROW_LIMIT_ENV, default=10_000),
    )


def load_http_port(environ: Mapping[str, str] | None = None) -> int:
    """Load Railway's HTTP port without echoing an invalid value."""
    source = os.environ if environ is None else environ
    raw_value = source.get(HTTP_PORT_ENV)
    if raw_value is None:
        return DEFAULT_HTTP_PORT
    try:
        port = int(raw_value)
    except ValueError as error:
        raise ValueError(f"environment variable {HTTP_PORT_ENV} must be an integer") from error
    if not 1 <= port <= 65_535:
        raise ValueError(f"environment variable {HTTP_PORT_ENV} must be between 1 and 65535")
    return port


def _required_value(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"required environment variable {name} is missing or empty")
    return value


def _positive_integer(environ: Mapping[str, str], name: str, *, default: int) -> int:
    raw_value = environ.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as error:
        raise ValueError(f"environment variable {name} must be an integer") from error
