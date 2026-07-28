"""Load normalized, reviewed Text-to-SQL examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from safe_text_to_sql.models import ExampleRecord
from safe_text_to_sql.sql.normalization import SQLNormalizationError, normalize_sql

_MAX_EXAMPLE_FILE_BYTES = 1_000_000


class ExampleLoadError(ValueError):
    """Raised when the local example file is missing or invalid."""


def load_examples(path: Path) -> tuple[ExampleRecord, ...]:
    """Load a bounded JSON list into immutable example records."""

    try:
        if path.stat().st_size > _MAX_EXAMPLE_FILE_BYTES:
            raise ExampleLoadError("Example file is too large.")
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExampleLoadError("Example file could not be loaded.") from exc

    if not isinstance(payload, list) or not payload:
        raise ExampleLoadError("Example file must contain a non-empty list.")

    examples: list[ExampleRecord] = []
    seen_ids: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ExampleLoadError("Every example must be an object.")
        example_id = _required_string(item, "id")
        if example_id in seen_ids:
            raise ExampleLoadError("Example IDs must be unique.")
        try:
            sql = normalize_sql(_required_string(item, "sql"))
        except SQLNormalizationError as exc:
            raise ExampleLoadError("Example SQL must not be empty.") from exc
        examples.append(
            ExampleRecord(
                example_id=example_id,
                question=_required_string(item, "question"),
                sql=sql,
            )
        )
        seen_ids.add(example_id)
    return tuple(examples)


def _required_string(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExampleLoadError(f"Example field '{key}' must be a non-empty string.")
    return value.strip()
