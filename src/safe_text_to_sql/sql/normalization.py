"""Conservative normalization for model-generated SQL text."""

from __future__ import annotations

import re

_COMPLETE_FENCE = re.compile(
    r"\A```(?:sql|postgresql)?[ \t]*\r?\n(?P<body>.*?)\r?\n?```[ \t]*\Z",
    re.IGNORECASE | re.DOTALL,
)
_LEADING_LABEL = re.compile(
    r"\A(?:sqlquery|sql|query)\s*:\s*",
    re.IGNORECASE,
)


class SQLNormalizationError(ValueError):
    """Raised when normalization does not produce SQL text."""


def normalize_sql(raw_output: str) -> str:
    """Remove safe presentation wrappers without rewriting SQL semantics."""

    normalized = raw_output.strip()
    fenced = _COMPLETE_FENCE.fullmatch(normalized)
    if fenced is not None:
        normalized = fenced.group("body").strip()

    normalized = _LEADING_LABEL.sub("", normalized, count=1).strip()
    while normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()

    if not normalized:
        raise SQLNormalizationError("Normalized SQL output is empty.")
    return normalized
