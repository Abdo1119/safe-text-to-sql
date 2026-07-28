"""Deterministic, network-free LLM provider for tests and local development."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Self

from safe_text_to_sql.llm.protocol import LLMProviderError
from safe_text_to_sql.models import (
    AnswerResponse,
    ExampleRecord,
    GeneratedSQLCandidate,
    QueryResult,
    UserQuestion,
    ValidatedSQLQuery,
    ValidationError,
    ValidationErrorCode,
)

Operation = Literal["generate_sql", "repair_sql", "generate_answer"]
_SUPPORTED_OPERATIONS: frozenset[str] = frozenset({"generate_sql", "repair_sql", "generate_answer"})


class FakeLLMError(LLMProviderError):
    """Configured deterministic provider failure."""


@dataclass(frozen=True, slots=True)
class RecordedLLMCall:
    """A safe record of one fake-provider invocation."""

    operation: Operation
    question: UserQuestion
    schema_context: str | None = None
    failed_sql: str | None = None
    error_code: ValidationErrorCode | None = None
    query: ValidatedSQLQuery | None = None
    result: QueryResult | None = None


class FakeLLMProvider:
    """Return configured values and record calls without network access."""

    provider_name = "fake"

    def __init__(
        self,
        *,
        generated_sql: str = "SELECT 1",
        repaired_sql: str | None = None,
        answer: str | None = "Deterministic offline answer.",
        fail_operations: Iterable[str] = (),
        sql_by_question: dict[str, str] | None = None,
    ) -> None:
        unsupported = frozenset(fail_operations) - _SUPPORTED_OPERATIONS
        if unsupported:
            raise ValueError("Unsupported fake-provider failure operation.")
        self._generated_sql = generated_sql
        self._repaired_sql = repaired_sql
        self._answer = answer
        self._fail_operations = frozenset(fail_operations)
        self._sql_by_question = sql_by_question or {}
        self._calls: list[RecordedLLMCall] = []

    @classmethod
    def from_examples(cls, examples: tuple[ExampleRecord, ...]) -> Self:
        """Create realistic deterministic presets from reviewed examples."""

        return cls(
            generated_sql=(
                "SELECT 'Offline fake mode supports the listed sample questions.' AS \"Message\""
            ),
            answer=None,
            sql_by_question={
                _normalize_question(example.question): example.sql for example in examples
            },
        )

    @property
    def calls(self) -> tuple[RecordedLLMCall, ...]:
        """Return an immutable snapshot of recorded calls."""

        return tuple(self._calls)

    async def generate_sql(
        self,
        question: UserQuestion,
        schema_context: str,
    ) -> GeneratedSQLCandidate:
        operation: Operation = "generate_sql"
        self._calls.append(
            RecordedLLMCall(
                operation=operation,
                question=question,
                schema_context=schema_context,
            )
        )
        self._raise_if_configured(operation)
        return GeneratedSQLCandidate(
            sql=self._sql_by_question.get(
                _normalize_question(question.text),
                self._generated_sql,
            ),
            provider=self.provider_name,
        )

    async def repair_sql(
        self,
        question: UserQuestion,
        failed_sql: str,
        error: ValidationError | str,
        schema_context: str,
    ) -> GeneratedSQLCandidate:
        operation: Operation = "repair_sql"
        error_code = error.code if isinstance(error, ValidationError) else None
        self._calls.append(
            RecordedLLMCall(
                operation=operation,
                question=question,
                schema_context=schema_context,
                failed_sql=failed_sql,
                error_code=error_code,
            )
        )
        self._raise_if_configured(operation)
        return GeneratedSQLCandidate(
            sql=self._repaired_sql or self._generated_sql,
            provider=self.provider_name,
        )

    async def generate_answer(
        self,
        question: UserQuestion,
        query: ValidatedSQLQuery,
        result: QueryResult,
    ) -> AnswerResponse:
        operation: Operation = "generate_answer"
        self._calls.append(
            RecordedLLMCall(
                operation=operation,
                question=question,
                query=query,
                result=result,
            )
        )
        self._raise_if_configured(operation)
        return AnswerResponse(
            question=question,
            answer=self._answer or _grounded_answer(result),
            query=query,
            result=result,
        )

    def _raise_if_configured(self, operation: Operation) -> None:
        if operation in self._fail_operations:
            raise FakeLLMError(f"Configured fake-provider failure: {operation}")


def _normalize_question(question: str) -> str:
    return " ".join(question.casefold().split())


def _grounded_answer(result: QueryResult) -> str:
    if not result.rows:
        return "No matching records were found."
    first_row = result.rows[0]
    first_summary = ", ".join(
        f"{column}: {value}" for column, value in zip(result.columns, first_row, strict=True)
    )
    if len(result.rows) == 1:
        return f"{first_summary}."
    return f"Returned {len(result.rows)} rows. First row — {first_summary}."
