from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from safe_text_to_sql.database.initializer import initialize_database
from safe_text_to_sql.database.sqlite import SQLiteRepository
from safe_text_to_sql.examples.loader import load_examples
from safe_text_to_sql.examples.selector import ExampleSelector
from safe_text_to_sql.llm.fake import FakeLLMProvider
from safe_text_to_sql.service import (
    ServiceError,
    ServiceErrorCode,
    TextToSQLService,
)


def _service(
    tmp_path: Path,
    provider: FakeLLMProvider,
    *,
    max_repair_attempts: int = 1,
    initialize: bool = True,
    allowed_tables: frozenset[str] | None = None,
) -> TextToSQLService:
    path = tmp_path / "demo.sqlite"
    if initialize:
        initialize_database(path)
    return TextToSQLService(
        provider=provider,
        repository=SQLiteRepository(path, max_rows=200),
        selector=ExampleSelector(load_examples(Path("data/examples.json"))),
        max_rows=200,
        max_repair_attempts=max_repair_attempts,
        example_top_k=3,
        max_question_chars=500,
        allowed_tables=allowed_tables,
        request_id_factory=lambda: "req-test",
    )


def test_happy_path_runs_generation_validation_execution_and_answer(tmp_path: Path) -> None:
    provider = FakeLLMProvider.from_examples(load_examples(Path("data/examples.json")))
    service = _service(tmp_path, provider)

    result = asyncio.run(service.ask("How many customers are in the USA?"))

    assert result.request_id == "req-test"
    assert result.candidate.provider == "fake"
    assert result.validated_query.referenced_tables == ("customer",)
    assert result.query_result.columns == ("TotalCustomers",)
    assert result.query_result.rows == ((3,),)
    assert result.answer.answer == "TotalCustomers: 3."
    assert len(result.selected_examples) == 3
    assert result.repair_attempts == 0
    assert [call.operation for call in provider.calls] == [
        "generate_sql",
        "generate_answer",
    ]


def test_invalid_generated_sql_is_repaired_before_execution(tmp_path: Path) -> None:
    provider = FakeLLMProvider(
        generated_sql='DELETE FROM "Customer"',
        repaired_sql='SELECT COUNT(*) AS TotalCustomers FROM "Customer"',
        answer="The database contains ten customers.",
    )
    service = _service(tmp_path, provider)

    result = asyncio.run(service.ask("How many customers exist?"))

    assert result.query_result.rows == ((10,),)
    assert result.repair_attempts == 1
    assert [call.operation for call in provider.calls] == [
        "generate_sql",
        "repair_sql",
        "generate_answer",
    ]


def test_invalid_question_never_calls_provider(tmp_path: Path) -> None:
    provider = FakeLLMProvider()
    service = _service(tmp_path, provider)

    with pytest.raises(ServiceError) as exc_info:
        asyncio.run(service.ask("   "))

    assert exc_info.value.code is ServiceErrorCode.INVALID_QUESTION
    assert provider.calls == ()


def test_validation_failure_stays_fail_closed_when_repairs_disabled(tmp_path: Path) -> None:
    provider = FakeLLMProvider(generated_sql='DROP TABLE "Customer"')
    service = _service(tmp_path, provider, max_repair_attempts=0)

    with pytest.raises(ServiceError) as exc_info:
        asyncio.run(service.ask("Delete customer data"))

    assert exc_info.value.code is ServiceErrorCode.SQL_VALIDATION
    assert [call.operation for call in provider.calls] == ["generate_sql"]


def test_missing_database_is_sanitized_before_provider_call(tmp_path: Path) -> None:
    provider = FakeLLMProvider(generated_sql="SELECT 1")
    service = _service(tmp_path, provider, max_repair_attempts=0, initialize=False)

    with pytest.raises(ServiceError) as exc_info:
        asyncio.run(service.ask("Return one"))

    assert exc_info.value.code is ServiceErrorCode.DATABASE
    assert str(tmp_path) not in str(exc_info.value)
    assert provider.calls == ()


def test_question_length_is_enforced_before_provider_call(tmp_path: Path) -> None:
    provider = FakeLLMProvider()
    service = TextToSQLService(
        provider=provider,
        repository=SQLiteRepository(tmp_path / "unused.sqlite", max_rows=10),
        selector=ExampleSelector(load_examples(Path("data/examples.json"))),
        max_rows=10,
        max_repair_attempts=0,
        example_top_k=1,
        max_question_chars=10,
        request_id_factory=lambda: "req-test",
    )

    with pytest.raises(ServiceError) as exc_info:
        asyncio.run(service.ask("This question is too long"))

    assert exc_info.value.code is ServiceErrorCode.INVALID_QUESTION
    assert provider.calls == ()


def test_configured_table_allowlist_narrows_introspected_schema(tmp_path: Path) -> None:
    provider = FakeLLMProvider(
        generated_sql='SELECT COUNT(*) FROM "Invoice"',
    )
    service = _service(
        tmp_path,
        provider,
        max_repair_attempts=0,
        allowed_tables=frozenset({"customer"}),
    )

    with pytest.raises(ServiceError) as exc_info:
        asyncio.run(service.ask("Count invoices"))

    assert exc_info.value.code is ServiceErrorCode.SQL_VALIDATION
    assert provider.calls[0].schema_context is not None
    assert '"Customer"' in provider.calls[0].schema_context
    assert '"Invoice"' not in provider.calls[0].schema_context
