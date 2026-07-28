from __future__ import annotations

from safe_text_to_sql.database.sqlite import serialize_sqlite_value


def test_serializes_supported_sqlite_values_without_loss() -> None:
    assert serialize_sqlite_value(None) is None
    assert serialize_sqlite_value(7) == 7
    assert serialize_sqlite_value(3.5) == 3.5
    assert serialize_sqlite_value("Ada") == "Ada"


def test_serializes_binary_values_without_exposing_content() -> None:
    assert serialize_sqlite_value(b"private-binary-content") == "<binary:22 bytes>"


def test_truncates_oversized_text_for_safe_rendering() -> None:
    rendered = serialize_sqlite_value("x" * 600)

    assert isinstance(rendered, str)
    assert len(rendered) == 501
    assert rendered.endswith("…")
