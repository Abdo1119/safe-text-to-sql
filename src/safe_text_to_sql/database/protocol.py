"""Database-independent repository contract."""

from __future__ import annotations

from typing import Protocol

from safe_text_to_sql.database.schema import DatabaseSchema
from safe_text_to_sql.models import QueryResult, ValidatedSQLQuery


class DatabaseRepository(Protocol):
    """Operations required by the application service."""

    def healthcheck(self) -> bool:
        """Return whether the configured database can answer a trivial query."""

        ...

    def introspect_schema(self) -> DatabaseSchema:
        """Return the public analytical schema."""

        ...

    def execute(self, query: ValidatedSQLQuery) -> QueryResult:
        """Execute one already-validated read-only query."""

        ...
