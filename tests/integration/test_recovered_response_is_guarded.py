"""Recovering an object from prose must not create a path around the SQL guard."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from safe_text_to_sql.config import SecretValue
from safe_text_to_sql.database.initializer import initialize_database
from safe_text_to_sql.database.sqlite import SQLiteRepository
from safe_text_to_sql.examples.loader import load_examples
from safe_text_to_sql.examples.selector import ExampleSelector
from safe_text_to_sql.llm.gemini import GeminiLLMProvider
from safe_text_to_sql.service import ServiceError, ServiceErrorCode, TextToSQLService


@dataclass
class _Response:
    text: str | None


class _Models:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = responses

    async def generate_content(self, **_kwargs: Any) -> _Response:
        return self._responses.pop(0)


class _AsyncClient:
    def __init__(self, models: _Models) -> None:
        self.models = models

    async def __aenter__(self) -> _AsyncClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _Client:
    def __init__(self, models: _Models) -> None:
        self.aio = _AsyncClient(models)


def _service(
    tmp_path: Path,
    responses: list[str],
    *,
    max_repair_attempts: int = 0,
) -> TextToSQLService:
    models = _Models([_Response(text) for text in responses])
    provider = GeminiLLMProvider(
        api_key=SecretValue("dummy-guard-test-key"),
        model="gemini-test",
        request_timeout_seconds=5,
        max_retries=0,
        client_factory=lambda **_kwargs: _Client(models),
    )
    database_path = tmp_path / "demo.sqlite"
    initialize_database(database_path)
    return TextToSQLService(
        provider=provider,
        repository=SQLiteRepository(database_path, max_rows=200),
        selector=ExampleSelector(load_examples(Path("data/examples.json"))),
        max_rows=200,
        max_repair_attempts=max_repair_attempts,
        example_top_k=3,
        max_question_chars=500,
        request_id_factory=lambda: "req-guard",
    )


def _wrapped(payload: dict[str, str]) -> str:
    """Wrap a valid object in the conversational prose observed from the provider."""

    return f"Here is the JSON requested:\n{json.dumps(payload)}\nHope that helps."


@pytest.mark.parametrize(
    ("label", "sql"),
    [
        ("drop", 'DROP TABLE "Track"'),
        ("delete", 'DELETE FROM "Track"'),
        ("update", 'UPDATE "Track" SET "Name" = \'x\''),
        ("two statements", 'SELECT 1; DROP TABLE "Track"'),
        ("system catalog", "SELECT * FROM sqlite_schema"),
        ("unknown table", 'SELECT * FROM "Secrets"'),
    ],
)
def test_prose_wrapped_unsafe_sql_is_still_rejected_by_the_guard(
    tmp_path: Path,
    label: str,
    sql: str,
) -> None:
    service = _service(tmp_path, [_wrapped({"sql": sql})])

    with pytest.raises(ServiceError) as exc_info:
        asyncio.run(service.ask("Remove every track from the catalogue"))

    assert exc_info.value.code is ServiceErrorCode.SQL_VALIDATION, label


def test_prose_wrapped_safe_sql_is_normalized_and_limited_like_any_other(
    tmp_path: Path,
) -> None:
    """A recovered query goes through the same normalization and row-limit policy."""

    service = _service(
        tmp_path,
        [
            _wrapped({"sql": 'SELECT "Name" FROM "Genre"'}),
            '```json\n{"answer":"Five genres are stored."}\n```',
        ],
    )

    result = asyncio.run(service.ask("List the genres"))

    assert result.validated_query.referenced_tables == ("genre",)
    assert result.validated_query.limit_was_added
    assert result.validated_query.effective_limit == 200
    assert result.validated_query.sql.endswith("LIMIT 200")
    assert result.answer.answer == "Five genres are stored."
