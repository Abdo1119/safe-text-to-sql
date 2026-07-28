"""Lightweight structured logging with conservative field redaction."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_SENSITIVE_FRAGMENTS = (
    "config",
    "credential",
    "key",
    "password",
    "path",
    "prompt",
    "row",
    "secret",
    "sql",
    "token",
)


class SafeJsonFormatter(logging.Formatter):
    """Format fixed events and pre-sanitized metadata as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", "application_log"),
        }
        safe_fields = getattr(record, "safe_fields", {})
        if isinstance(safe_fields, Mapping):
            payload.update(
                {str(key): _safe_value(str(key), value) for key, value in safe_fields.items()}
            )
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def configure_logging(level: str) -> logging.Logger:
    """Configure the project logger once without file output."""

    logger = logging.getLogger("safe_text_to_sql")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(SafeJsonFormatter())
        logger.addHandler(handler)
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    request_id: str | None = None,
    **safe_fields: Any,
) -> None:
    """Emit a fixed event name and fields that are redacted by key."""

    fields = dict(safe_fields)
    if request_id is not None:
        fields["request_id"] = request_id
    logger.info(
        event,
        extra={
            "event": event,
            "safe_fields": fields,
        },
    )


def _safe_value(key: str, value: Any) -> object:
    normalized_key = key.casefold()
    if any(fragment in normalized_key for fragment in _SENSITIVE_FRAGMENTS):
        return "[REDACTED]"
    if value is None or isinstance(value, (bool, float, int, str)):
        return value
    return str(value)
