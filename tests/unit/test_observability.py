from __future__ import annotations

import io
import json
import logging

from safe_text_to_sql.observability import SafeJsonFormatter, log_event


def test_structured_logging_keeps_safe_fields_and_redacts_sensitive_fields() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SafeJsonFormatter())
    logger = logging.getLogger("safe-text-to-sql-test")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_event(
        logger,
        "request_failed",
        request_id="req-123",
        provider="fake",
        error_category="validation",
        api_key="private-key-value",
        prompt="private prompt",
        rows=[["private row"]],
    )

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "request_failed"
    assert payload["request_id"] == "req-123"
    assert payload["provider"] == "fake"
    assert payload["error_category"] == "validation"
    assert payload["api_key"] == "[REDACTED]"
    assert payload["prompt"] == "[REDACTED]"
    assert payload["rows"] == "[REDACTED]"
    assert "private-key-value" not in stream.getvalue()
    assert "private row" not in stream.getvalue()
