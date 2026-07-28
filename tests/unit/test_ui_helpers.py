from __future__ import annotations

from safe_text_to_sql.config import Settings
from safe_text_to_sql.models import ValidatedSQLQuery
from safe_text_to_sql.service import ServiceError, ServiceErrorCode
from safe_text_to_sql.ui import (
    safe_configuration_summary,
    safe_error_message,
    safe_unexpected_error_message,
    validation_summary,
)


def test_configuration_summary_excludes_secrets_and_local_paths() -> None:
    private_path = "private/local/demo.sqlite"
    private_key = "dummy-private-key"
    settings = Settings.from_env(
        {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": private_key,
            "DATABASE_PATH": private_path,
        }
    )

    summary = safe_configuration_summary(settings, example_count=25)
    rendered = repr(summary)

    assert summary["Provider"] == "Gemini"
    assert summary["Model"] == "gemini-2.5-flash"
    assert summary["Examples"] == "25 reviewed / top 3"
    assert private_path not in rendered
    assert private_key not in rendered


def test_validation_summary_reports_guard_actions() -> None:
    query = ValidatedSQLQuery(
        sql="SELECT 1 LIMIT 200",
        referenced_tables=(),
        effective_limit=200,
        limit_was_added=True,
        limit_was_clamped=False,
    )

    summary = validation_summary(query, repair_attempts=1)

    assert summary == {
        "Policy": "Passed",
        "Row limit": "Added (200)",
        "Repair attempts": "1",
        "Tables": "No physical tables",
    }


def test_safe_error_message_contains_category_and_request_id_only() -> None:
    error = ServiceError(
        ServiceErrorCode.DATABASE,
        "The demo database is unavailable.",
        request_id="req-safe",
    )

    message = safe_error_message(error)

    assert message == ("The demo database is unavailable. Reference: req-safe (database).")


def test_unexpected_error_message_never_contains_exception_details() -> None:
    private_detail = "private-unexpected-runtime-detail"

    message = safe_unexpected_error_message(RuntimeError(private_detail))

    assert private_detail not in message
    assert message == "The request could not be completed safely. Try again."
