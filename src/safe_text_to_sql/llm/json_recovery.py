"""Bounded recovery of one JSON object from a response wrapped in prose.

Structured output remains the contract. A model occasionally emits a conversational
prefix or a Markdown fence around an otherwise valid object, and this recovers that
single object without loosening what counts as a valid response. It never repairs,
completes, or reinterprets the payload: the object is either present and complete, or
the caller treats the response as invalid.
"""

from __future__ import annotations

import json

_MAX_SCANNED_CHARACTERS = 200_000


def extract_single_json_object(text: str) -> dict[str, object] | None:
    """Return the one complete top-level JSON object in ``text``.

    Returns ``None`` — meaning the caller must reject the response — when the text
    holds no complete object, more than one, or anything that is not an object. A
    truncated object anywhere in the text rejects the whole response rather than
    letting a partial payload through alongside a complete one.
    """

    if len(text) > _MAX_SCANNED_CHARACTERS:
        return None

    spans = _top_level_object_spans(text)
    if spans is None or len(spans) != 1:
        return None

    start, end = spans[0]
    try:
        candidate = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None
    if not isinstance(candidate, dict):
        return None
    return candidate


def _top_level_object_spans(text: str) -> list[tuple[int, int]] | None:
    """Locate balanced top-level ``{...}`` spans, or ``None`` if one is unterminated.

    Scanning is string-aware, because braces and escaped quotes inside JSON string
    values must not change nesting depth: otherwise ``{"sql": "SELECT '{'"}`` looks
    unbalanced. Brackets are tracked too, so an object nested in an array is not
    mistaken for the payload — unwrapping ``[{...}]`` would be guessing which element
    was meant.
    """

    spans: list[tuple[int, int]] = []
    brace_depth = 0
    bracket_depth = 0
    start = -1
    in_string = False
    escaped = False

    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            # Quotes only delimit strings inside a structure; in surrounding prose they
            # are ordinary punctuation.
            if brace_depth > 0 or bracket_depth > 0:
                in_string = True
            continue
        if character == "[":
            bracket_depth += 1
        elif character == "]":
            # A stray closer in prose is not a structure boundary.
            bracket_depth = max(0, bracket_depth - 1)
        elif character == "{":
            if brace_depth == 0 and bracket_depth == 0:
                start = index
            brace_depth += 1
        elif character == "}":
            if brace_depth == 0:
                continue
            brace_depth -= 1
            if brace_depth == 0 and bracket_depth == 0:
                spans.append((start, index + 1))

    if brace_depth != 0:
        return None
    return spans
