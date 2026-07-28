from __future__ import annotations

import pytest

from safe_text_to_sql.sql.normalization import (
    SQLNormalizationError,
    normalize_sql,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("```sql\nSELECT 1;\n```", "SELECT 1"),
        ("```postgresql\r\nSELECT 2\r\n```", "SELECT 2"),
        ("```\nSELECT 3\n```", "SELECT 3"),
    ],
)
def test_removes_complete_markdown_sql_fences(raw: str, expected: str) -> None:
    assert normalize_sql(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SQL: SELECT 1", "SELECT 1"),
        ("sqlquery: SELECT 2", "SELECT 2"),
        ("Query: SELECT 3", "SELECT 3"),
    ],
)
def test_removes_harmless_leading_labels(raw: str, expected: str) -> None:
    assert normalize_sql(raw) == expected


def test_trims_whitespace_and_trailing_semicolons() -> None:
    assert normalize_sql(" \n SELECT 1;;; \t") == "SELECT 1"


def test_preserves_string_literals_and_identifier_case() -> None:
    raw = "SQL: SELECT 'SQL: Keep This; MixedCase' AS \"MixedCase\";"

    normalized = normalize_sql(raw)

    assert normalized == "SELECT 'SQL: Keep This; MixedCase' AS \"MixedCase\""


def test_does_not_hide_multiple_statements() -> None:
    normalized = normalize_sql("SELECT 1; DROP TABLE users;")

    assert normalized == "SELECT 1; DROP TABLE users"


@pytest.mark.parametrize("raw", ["", "   ", "SQL:", "```sql\n \n```", ";;;"])
def test_rejects_empty_normalized_output(raw: str) -> None:
    with pytest.raises(SQLNormalizationError, match="empty"):
        normalize_sql(raw)


def test_does_not_extract_sql_from_surrounding_explanation() -> None:
    raw = "Here is the query:\n```sql\nSELECT 1\n```"

    assert normalize_sql(raw) == raw
