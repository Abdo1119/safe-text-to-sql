"""Typed, import-safe application configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

EnumType = TypeVar("EnumType", bound=StrEnum)


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


class AppEnvironment(StrEnum):
    """Supported application environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LLMProviderMode(StrEnum):
    """Configured LLM provider implementation."""

    FAKE = "fake"
    GEMINI = "gemini"


@dataclass(frozen=True, slots=True)
class SecretValue:
    """A secret string that is masked in text and object representations."""

    _value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self._value:
            raise ConfigError("Secret values must not be empty.")

    def get_secret_value(self) -> str:
        """Return the underlying value for an authorized adapter."""

        return self._value

    def __str__(self) -> str:
        return "********"

    def __repr__(self) -> str:
        return "<secret>"


@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings created explicitly from an environment mapping."""

    environment: AppEnvironment
    llm_provider: LLMProviderMode
    database_path: Path = field(repr=False)
    max_returned_rows: int
    max_repair_attempts: int
    example_top_k: int
    max_question_chars: int
    allowed_schemas: frozenset[str]
    allowed_tables: frozenset[str] | None
    log_level: str
    gemini_model: str
    gemini_request_timeout_seconds: float
    gemini_max_retries: int
    gemini_api_key: SecretValue | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings without reading environment variables at import time."""

        values = os.environ if environ is None else environ
        environment = _parse_enum(
            values.get("APP_ENV", AppEnvironment.DEVELOPMENT.value),
            AppEnvironment,
            "APP_ENV",
        )
        provider = _parse_enum(
            values.get("LLM_PROVIDER", LLMProviderMode.FAKE.value),
            LLMProviderMode,
            "LLM_PROVIDER",
        )
        raw_database_path = values.get(
            "DATABASE_PATH",
            "data/demo/chinook_demo.sqlite",
        ).strip()
        if not raw_database_path:
            raise ConfigError("DATABASE_PATH must not be empty.")
        database_path = Path(raw_database_path)
        max_rows = _parse_positive_int(
            values.get("MAX_RETURNED_ROWS", "200"),
            "MAX_RETURNED_ROWS",
        )
        max_repair_attempts = _parse_non_negative_int(
            values.get("MAX_REPAIR_ATTEMPTS", "1"),
            "MAX_REPAIR_ATTEMPTS",
        )
        example_top_k = _parse_positive_int(
            values.get("EXAMPLE_TOP_K", "3"),
            "EXAMPLE_TOP_K",
        )
        max_question_chars = _parse_positive_int(
            values.get("MAX_QUESTION_CHARS", "500"),
            "MAX_QUESTION_CHARS",
        )
        allowed_schemas = _parse_allowlist(
            values.get("ALLOWED_SCHEMAS"),
            empty_value=frozenset(),
        )
        allowed_tables = _parse_allowlist(
            values.get("ALLOWED_TABLES"),
            empty_value=None,
        )
        log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigError("LOG_LEVEL must be a supported logging level.")

        gemini_model = values.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
        if not gemini_model:
            raise ConfigError("GEMINI_MODEL must not be empty.")
        request_timeout = _parse_positive_float(
            values.get("GEMINI_REQUEST_TIMEOUT_SECONDS", "30"),
            "GEMINI_REQUEST_TIMEOUT_SECONDS",
        )
        max_retries = _parse_non_negative_int(
            values.get("GEMINI_MAX_RETRIES", "2"),
            "GEMINI_MAX_RETRIES",
        )
        raw_api_key = values.get("GEMINI_API_KEY", "").strip()
        api_key = SecretValue(raw_api_key) if raw_api_key else None
        if provider is LLMProviderMode.GEMINI and api_key is None:
            raise ConfigError("GEMINI_API_KEY is required when LLM_PROVIDER is gemini.")

        return cls(
            environment=environment,
            llm_provider=provider,
            database_path=database_path,
            max_returned_rows=max_rows,
            max_repair_attempts=max_repair_attempts,
            example_top_k=example_top_k,
            max_question_chars=max_question_chars,
            allowed_schemas=allowed_schemas or frozenset(),
            allowed_tables=allowed_tables,
            log_level=log_level,
            gemini_model=gemini_model,
            gemini_request_timeout_seconds=request_timeout,
            gemini_max_retries=max_retries,
            gemini_api_key=api_key,
        )


def _parse_positive_int(raw_value: str, variable_name: str) -> int:
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{variable_name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ConfigError(f"{variable_name} must be a positive integer.")
    return parsed


def _parse_non_negative_int(raw_value: str, variable_name: str) -> int:
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{variable_name} must be a non-negative integer.") from exc
    if parsed < 0:
        raise ConfigError(f"{variable_name} must be a non-negative integer.")
    return parsed


def _parse_positive_float(raw_value: str, variable_name: str) -> float:
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{variable_name} must be a positive number.") from exc
    if parsed <= 0:
        raise ConfigError(f"{variable_name} must be a positive number.")
    return parsed


def _parse_allowlist(
    raw_value: str | None,
    *,
    empty_value: frozenset[str] | None,
) -> frozenset[str] | None:
    if raw_value is None or not raw_value.strip():
        return empty_value
    return frozenset(item.strip().casefold() for item in raw_value.split(",") if item.strip())


def _parse_enum(
    raw_value: str,
    enum_type: type[EnumType],
    variable_name: str,
) -> EnumType:
    try:
        return enum_type(raw_value.strip().casefold())
    except ValueError as exc:
        raise ConfigError(f"{variable_name} has an unsupported value.") from exc
