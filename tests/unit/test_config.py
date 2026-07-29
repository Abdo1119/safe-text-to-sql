from __future__ import annotations

from pathlib import Path

import pytest

from safe_text_to_sql.config import (
    AppEnvironment,
    ConfigError,
    LLMProviderMode,
    Settings,
)
from safe_text_to_sql.models import (
    GeneratedSQLCandidate,
    QueryResult,
    UserQuestion,
)


def test_fake_mode_uses_safe_offline_defaults() -> None:
    settings = Settings.from_env({})

    assert settings.environment is AppEnvironment.DEVELOPMENT
    assert settings.llm_provider is LLMProviderMode.FAKE
    assert settings.database_path == Path("data/demo/chinook_demo.sqlite")
    assert settings.max_returned_rows == 200
    assert settings.max_repair_attempts == 1
    assert settings.example_top_k == 3
    assert settings.gemini_model == "gemini-3.6-flash"
    assert settings.gemini_request_timeout_seconds == 30.0
    assert settings.gemini_max_retries == 2
    assert settings.allowed_schemas == frozenset()
    assert settings.allowed_tables is None
    assert settings.gemini_api_key is None


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAX_RETURNED_ROWS", "0"),
        ("MAX_RETURNED_ROWS", "-10"),
        ("MAX_REPAIR_ATTEMPTS", "-1"),
        ("EXAMPLE_TOP_K", "0"),
        ("GEMINI_REQUEST_TIMEOUT_SECONDS", "0"),
        ("GEMINI_MAX_RETRIES", "-1"),
    ],
)
def test_invalid_numeric_settings_fail_without_echoing_values(
    name: str,
    value: str,
) -> None:
    with pytest.raises(ConfigError) as exc_info:
        Settings.from_env({name: value})

    assert value not in str(exc_info.value)
    assert name in str(exc_info.value)


def test_secret_values_are_hidden_from_repr_and_str() -> None:
    api_key = "unit-test-api-key-that-must-stay-hidden"
    database_path = "private/local/demo.sqlite"

    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": api_key,
            "DATABASE_PATH": database_path,
        }
    )

    rendered = repr(settings)
    assert api_key not in rendered
    assert database_path not in rendered
    assert settings.gemini_api_key is not None
    assert str(settings.gemini_api_key) == "********"
    assert settings.gemini_api_key.get_secret_value() == api_key


def test_allowlists_parse_trim_and_deduplicate() -> None:
    settings = Settings.from_env(
        {
            "ALLOWED_SCHEMAS": " public, analytics,public ",
            "ALLOWED_TABLES": " Customer, public.Invoice,customer ",
        }
    )

    assert settings.allowed_schemas == frozenset({"public", "analytics"})
    assert settings.allowed_tables == frozenset({"customer", "public.invoice"})


def test_gemini_mode_requires_api_key_without_revealing_configuration() -> None:
    with pytest.raises(ConfigError) as exc_info:
        Settings.from_env(
            {
                "LLM_PROVIDER": "gemini",
                "DATABASE_PATH": "private/local/demo.sqlite",
            }
        )

    assert "GEMINI_API_KEY" in str(exc_info.value)
    assert "private/local/demo.sqlite" not in str(exc_info.value)


def test_gemini_configuration_uses_explicit_model_and_retry_settings() -> None:
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "dummy-test-key",
            "GEMINI_MODEL": "gemini-test-model",
            "GEMINI_REQUEST_TIMEOUT_SECONDS": "12.5",
            "GEMINI_MAX_RETRIES": "1",
        }
    )

    assert settings.llm_provider is LLMProviderMode.GEMINI
    assert settings.gemini_model == "gemini-test-model"
    assert settings.gemini_request_timeout_seconds == 12.5
    assert settings.gemini_max_retries == 1


def test_user_question_rejects_blank_text() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        UserQuestion("   ")


def test_domain_models_normalize_collection_inputs() -> None:
    candidate = GeneratedSQLCandidate(sql="SELECT 1", provider="fake")
    result = QueryResult(columns=("value",), rows=((1,),))

    assert candidate.sql == "SELECT 1"
    assert result.columns == ("value",)
    assert result.rows == ((1,),)
