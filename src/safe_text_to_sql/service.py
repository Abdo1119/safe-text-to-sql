"""Framework-independent Text-to-SQL orchestration service."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from enum import StrEnum

from safe_text_to_sql.database.protocol import DatabaseRepository
from safe_text_to_sql.database.sqlite import DatabaseError, DatabaseErrorCode
from safe_text_to_sql.examples.selector import ExampleSelector
from safe_text_to_sql.llm.protocol import LLMProvider, LLMProviderError
from safe_text_to_sql.models import (
    GeneratedSQLCandidate,
    QueryResult,
    UserQuestion,
    ValidatedSQLQuery,
    WorkflowResult,
)
from safe_text_to_sql.observability import log_event
from safe_text_to_sql.prompting.templates import build_generation_context
from safe_text_to_sql.sql.guard import SQLGuard
from safe_text_to_sql.sql.policies import SQLPolicy


class ServiceErrorCode(StrEnum):
    """Safe application failure categories."""

    INVALID_QUESTION = "invalid_question"
    PROVIDER = "provider"
    SQL_VALIDATION = "sql_validation"
    DATABASE = "database"


class ServiceError(RuntimeError):
    """Safe orchestration failure suitable for the UI."""

    def __init__(
        self,
        code: ServiceErrorCode,
        message: str,
        *,
        request_id: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id


class TextToSQLService:
    """Coordinate generation, validation, bounded repair, execution, and answer."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        repository: DatabaseRepository,
        selector: ExampleSelector,
        max_rows: int,
        max_repair_attempts: int,
        example_top_k: int,
        max_question_chars: int,
        request_id_factory: Callable[[], str] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if max_rows <= 0 or example_top_k <= 0 or max_question_chars <= 0:
            raise ValueError("Service limits must be positive.")
        if max_repair_attempts < 0:
            raise ValueError("max_repair_attempts must be non-negative.")
        self._provider = provider
        self._repository = repository
        self._selector = selector
        self._max_rows = max_rows
        self._max_repair_attempts = max_repair_attempts
        self._example_top_k = example_top_k
        self._max_question_chars = max_question_chars
        self._request_id_factory = request_id_factory or (lambda: uuid.uuid4().hex[:12])
        self._logger = logger or logging.getLogger("safe_text_to_sql.service")

    async def ask(self, raw_question: str) -> WorkflowResult:
        """Run one request without exposing prompts, SQL, rows, or internal errors."""

        request_id = self._request_id_factory()
        question = self._validate_question(raw_question, request_id)
        log_event(
            self._logger,
            "request_started",
            request_id=request_id,
            provider=self._provider.provider_name,
        )

        try:
            schema = self._repository.introspect_schema()
        except DatabaseError as exc:
            log_event(
                self._logger,
                "request_failed",
                request_id=request_id,
                provider=self._provider.provider_name,
                error_category="database",
            )
            raise ServiceError(
                ServiceErrorCode.DATABASE,
                str(exc),
                request_id=request_id,
            ) from exc
        selections = self._selector.select(question.text, top_k=self._example_top_k)
        generation_context = build_generation_context(
            schema.render_for_prompt(),
            selections,
        )
        guard = SQLGuard(
            SQLPolicy(
                allowed_schemas=frozenset(),
                allowed_tables=schema.allowed_tables,
                max_rows=self._max_rows,
            )
        )

        try:
            candidate = await self._provider.generate_sql(question, generation_context)
            (
                candidate,
                validated_query,
                query_result,
                repair_attempts,
            ) = await self._validate_and_execute(
                question=question,
                candidate=candidate,
                generation_context=generation_context,
                guard=guard,
                request_id=request_id,
            )
            answer = await self._provider.generate_answer(
                question,
                validated_query,
                query_result,
            )
        except LLMProviderError as exc:
            log_event(
                self._logger,
                "request_failed",
                request_id=request_id,
                provider=self._provider.provider_name,
                error_category="provider",
            )
            raise ServiceError(
                ServiceErrorCode.PROVIDER,
                str(exc),
                request_id=request_id,
            ) from exc

        log_event(
            self._logger,
            "request_completed",
            request_id=request_id,
            provider=self._provider.provider_name,
            repair_attempts=repair_attempts,
            result_count=len(query_result.rows),
        )
        return WorkflowResult(
            request_id=request_id,
            question=question,
            candidate=candidate,
            validated_query=validated_query,
            query_result=query_result,
            answer=answer,
            selected_examples=selections,
            repair_attempts=repair_attempts,
        )

    async def _validate_and_execute(
        self,
        *,
        question: UserQuestion,
        candidate: GeneratedSQLCandidate,
        generation_context: str,
        guard: SQLGuard,
        request_id: str,
    ) -> tuple[GeneratedSQLCandidate, ValidatedSQLQuery, QueryResult, int]:
        repair_attempts = 0
        current = candidate
        while True:
            validation = guard.validate(current.sql)
            if not validation.is_valid or validation.query is None:
                if repair_attempts >= self._max_repair_attempts:
                    raise ServiceError(
                        ServiceErrorCode.SQL_VALIDATION,
                        "The generated query did not pass the read-only safety policy.",
                        request_id=request_id,
                    )
                error = validation.errors[0]
                current = await self._provider.repair_sql(
                    question,
                    current.sql,
                    error,
                    generation_context,
                )
                repair_attempts += 1
                continue

            try:
                query_result = self._repository.execute(validation.query)
            except DatabaseError as exc:
                can_repair = (
                    exc.code
                    in {
                        DatabaseErrorCode.EXECUTION_FAILED,
                        DatabaseErrorCode.QUERY_REJECTED,
                    }
                    and repair_attempts < self._max_repair_attempts
                )
                if can_repair:
                    current = await self._provider.repair_sql(
                        question,
                        current.sql,
                        f"database_{exc.code.value}",
                        generation_context,
                    )
                    repair_attempts += 1
                    continue
                raise ServiceError(
                    ServiceErrorCode.DATABASE,
                    str(exc),
                    request_id=request_id,
                ) from exc
            return current, validation.query, query_result, repair_attempts

    def _validate_question(self, raw_question: str, request_id: str) -> UserQuestion:
        try:
            question = UserQuestion(raw_question)
        except ValueError as exc:
            raise ServiceError(
                ServiceErrorCode.INVALID_QUESTION,
                "Enter a non-empty analytics question.",
                request_id=request_id,
            ) from exc
        if len(question.text) > self._max_question_chars:
            raise ServiceError(
                ServiceErrorCode.INVALID_QUESTION,
                f"Keep the question under {self._max_question_chars} characters.",
                request_id=request_id,
            )
        return question
