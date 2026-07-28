"""Provider-independent asynchronous LLM contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from safe_text_to_sql.models import (
    AnswerResponse,
    GeneratedSQLCandidate,
    QueryResult,
    UserQuestion,
    ValidatedSQLQuery,
    ValidationError,
)


class LLMProviderError(RuntimeError):
    """Base class for safe provider failures."""


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal operations required from an LLM provider."""

    @property
    def provider_name(self) -> str:
        """Return a safe provider label for observability and UI status."""

        ...

    async def generate_sql(
        self,
        question: UserQuestion,
        schema_context: str,
    ) -> GeneratedSQLCandidate:
        """Generate a SQL candidate from a question and database schema."""

        ...

    async def repair_sql(
        self,
        question: UserQuestion,
        failed_sql: str,
        error: ValidationError | str,
        schema_context: str,
    ) -> GeneratedSQLCandidate:
        """Generate a corrected SQL candidate after a safe error."""

        ...

    async def generate_answer(
        self,
        question: UserQuestion,
        query: ValidatedSQLQuery,
        result: QueryResult,
    ) -> AnswerResponse:
        """Generate a grounded answer from validated SQL and result rows."""

        ...
