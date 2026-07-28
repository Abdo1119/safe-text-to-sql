"""Provider- and framework-independent domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


@dataclass(frozen=True, slots=True)
class UserQuestion:
    """A validated natural-language question."""

    text: str

    def __post_init__(self) -> None:
        normalized = self.text.strip()
        if not normalized:
            raise ValueError("User question must not be blank.")
        object.__setattr__(self, "text", normalized)


@dataclass(frozen=True, slots=True)
class ExampleRecord:
    """One reviewed natural-language and SQL example."""

    example_id: str
    question: str
    sql: str

    def __post_init__(self) -> None:
        if not self.example_id.strip():
            raise ValueError("Example ID must not be blank.")
        if not self.question.strip():
            raise ValueError("Example question must not be blank.")
        if not self.sql.strip():
            raise ValueError("Example SQL must not be blank.")


@dataclass(frozen=True, slots=True)
class SelectedExample:
    """An example selected with transparent lexical metadata."""

    example: ExampleRecord
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedSQLCandidate:
    """Raw SQL produced by an LLM provider."""

    sql: str
    provider: str

    def __post_init__(self) -> None:
        if not self.sql.strip():
            raise ValueError("Generated SQL candidate must not be blank.")


@dataclass(frozen=True, slots=True)
class ValidatedSQLQuery:
    """A parsed and policy-approved PostgreSQL query."""

    sql: str
    referenced_tables: tuple[str, ...]
    effective_limit: int
    limit_was_added: bool
    limit_was_clamped: bool


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Database-independent tabular query output."""

    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    truncated: bool = False

    def __post_init__(self) -> None:
        expected_width = len(self.columns)
        if any(len(row) != expected_width for row in self.rows):
            raise ValueError("Every result row must match the number of columns.")


@dataclass(frozen=True, slots=True)
class AnswerResponse:
    """Natural-language answer and the evidence used to produce it."""

    question: UserQuestion
    answer: str
    query: ValidatedSQLQuery
    result: QueryResult

    def __post_init__(self) -> None:
        if not self.answer.strip():
            raise ValueError("Answer text must not be blank.")


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Complete safe application result for presentation and evaluation."""

    request_id: str
    question: UserQuestion
    candidate: GeneratedSQLCandidate
    validated_query: ValidatedSQLQuery
    query_result: QueryResult
    answer: AnswerResponse
    selected_examples: tuple[SelectedExample, ...]
    repair_attempts: int


class ValidationErrorCode(StrEnum):
    """Stable machine-readable SQL validation outcomes."""

    EMPTY_SQL = "empty_sql"
    PARSE_ERROR = "parse_error"
    MULTIPLE_STATEMENTS = "multiple_statements"
    DISALLOWED_STATEMENT = "disallowed_statement"
    DATA_MODIFYING_CTE = "data_modifying_cte"
    SELECT_INTO = "select_into"
    LOCKING_CLAUSE = "locking_clause"
    UNAUTHORIZED_SCHEMA = "unauthorized_schema"
    UNAUTHORIZED_TABLE = "unauthorized_table"
    SYSTEM_CATALOG = "system_catalog"
    INVALID_LIMIT = "invalid_limit"
    EXCESSIVE_LIMIT = "excessive_limit"


@dataclass(frozen=True, slots=True)
class ValidationError:
    """A safe SQL validation error suitable for machine and UI handling."""

    code: ValidationErrorCode
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """The successful query or one or more validation errors."""

    query: ValidatedSQLQuery | None
    errors: tuple[ValidationError, ...] = ()

    def __post_init__(self) -> None:
        if (self.query is None) == (not self.errors):
            raise ValueError("ValidationResult must contain either a query or errors.")

    @property
    def is_valid(self) -> bool:
        """Whether validation produced an executable read-only query."""

        return self.query is not None

    @classmethod
    def success(cls, query: ValidatedSQLQuery) -> ValidationResult:
        return cls(query=query)

    @classmethod
    def failure(cls, *errors: ValidationError) -> ValidationResult:
        if not errors:
            raise ValueError("At least one validation error is required.")
        return cls(query=None, errors=tuple(errors))
