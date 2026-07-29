from __future__ import annotations

import pytest

from safe_text_to_sql.llm.json_recovery import extract_single_json_object


def test_clean_json_object_is_returned_unchanged() -> None:
    assert extract_single_json_object('{"sql": "SELECT 1"}') == {"sql": "SELECT 1"}


def test_prose_prefix_is_ignored() -> None:
    """The observed live behaviour: a conversational lead-in before the object."""

    text = 'Here is the JSON requested:\n{"sql": "SELECT 1"}'

    assert extract_single_json_object(text) == {"sql": "SELECT 1"}


def test_prose_suffix_is_ignored() -> None:
    text = '{"sql": "SELECT 1"}\nLet me know if you need anything else.'

    assert extract_single_json_object(text) == {"sql": "SELECT 1"}


def test_prose_on_both_sides_is_ignored() -> None:
    text = 'Sure! Here you go:\n{"sql": "SELECT 1"}\nHope that helps.'

    assert extract_single_json_object(text) == {"sql": "SELECT 1"}


def test_markdown_code_fence_is_ignored() -> None:
    text = '```json\n{"sql": "SELECT 1"}\n```'

    assert extract_single_json_object(text) == {"sql": "SELECT 1"}


def test_braces_inside_string_values_do_not_break_boundary_detection() -> None:
    """A brace inside a SQL literal must not be read as nesting."""

    text = "Result:\n{\"sql\": \"SELECT '{' AS opener, '}' AS closer\"}"

    assert extract_single_json_object(text) == {"sql": "SELECT '{' AS opener, '}' AS closer"}


def test_escaped_quotes_inside_string_values_are_handled() -> None:
    text = 'Result: {"sql": "SELECT \\"Name\\" FROM \\"Track\\""}'

    assert extract_single_json_object(text) == {"sql": 'SELECT "Name" FROM "Track"'}


def test_nested_objects_are_returned_whole() -> None:
    text = 'Here: {"sql": "SELECT 1", "meta": {"note": "nested"}}'

    assert extract_single_json_object(text) == {"sql": "SELECT 1", "meta": {"note": "nested"}}


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("two objects", '{"sql": "SELECT 1"} and {"sql": "SELECT 2"}'),
        ("two objects on separate lines", '{"sql": "SELECT 1"}\n{"sql": "SELECT 2"}'),
        ("truncated object", '{"sql": "SELECT 1"'),
        ("truncated after a complete object", '{"sql": "SELECT 1"} then {"sql":'),
        ("unterminated string", '{"sql": "SELECT 1}'),
        ("malformed json", "{sql: SELECT 1}"),
        ("trailing comma", '{"sql": "SELECT 1",}'),
        ("array payload", '[{"sql": "SELECT 1"}]'),
        ("bare array", "[1, 2, 3]"),
        ("scalar payload", '"SELECT 1"'),
        ("number payload", "42"),
        ("prose only", "I could not produce SQL for that question."),
        ("empty text", ""),
        ("stray closing brace only", "}"),
    ],
)
def test_ambiguous_or_invalid_payloads_are_rejected(label: str, text: str) -> None:
    assert extract_single_json_object(text) is None, label


def test_an_array_wrapped_in_prose_is_rejected_because_an_object_is_required() -> None:
    assert extract_single_json_object('Here: [{"sql": "SELECT 1"}]') is None


def test_oversized_text_is_rejected_without_scanning() -> None:
    assert extract_single_json_object('{"sql": "x"}' + " " * 200_001) is None
