"""Read-only SQLite repository with database-level policy enforcement."""

from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote

from safe_text_to_sql.database.schema import (
    ColumnSchema,
    DatabaseSchema,
    TableSchema,
)
from safe_text_to_sql.models import QueryResult, ValidatedSQLQuery

_ALLOWED_AUTHORIZER_ACTIONS = frozenset(
    action
    for action in (
        getattr(sqlite3, "SQLITE_FUNCTION", None),
        getattr(sqlite3, "SQLITE_READ", None),
        getattr(sqlite3, "SQLITE_RECURSIVE", None),
        getattr(sqlite3, "SQLITE_SELECT", None),
    )
    if action is not None
)


class DatabaseErrorCode(StrEnum):
    """Safe database failure categories."""

    UNAVAILABLE = "unavailable"
    QUERY_REJECTED = "query_rejected"
    EXECUTION_FAILED = "execution_failed"


class DatabaseError(RuntimeError):
    """Database failure without paths, SQL, or driver details."""

    def __init__(self, code: DatabaseErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class SQLiteRepository:
    """Execute validated analytics against a fixed read-only SQLite file."""

    def __init__(self, path: Path, *, max_rows: int) -> None:
        if max_rows <= 0:
            raise ValueError("max_rows must be positive.")
        self._path = path
        self._max_rows = max_rows

    def healthcheck(self) -> bool:
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT 1").fetchone()
        except (OSError, sqlite3.DatabaseError) as exc:
            raise DatabaseError(
                DatabaseErrorCode.UNAVAILABLE,
                "The demo database is unavailable. Run the initialization command.",
            ) from exc
        return bool(row == (1,))

    def introspect_schema(self) -> DatabaseSchema:
        try:
            with self._connect() as connection:
                table_rows = connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                ).fetchall()
                tables = tuple(
                    TableSchema(
                        name=str(row[0]),
                        columns=self._columns_for_table(connection, str(row[0])),
                    )
                    for row in table_rows
                )
        except (OSError, sqlite3.DatabaseError) as exc:
            raise DatabaseError(
                DatabaseErrorCode.UNAVAILABLE,
                "The demo database schema is unavailable.",
            ) from exc
        return DatabaseSchema(tables=tables)

    def execute(self, query: ValidatedSQLQuery) -> QueryResult:
        try:
            with self._connect() as connection:
                connection.set_authorizer(_read_only_authorizer)
                cursor = connection.execute(query.sql)
                if cursor.description is None:
                    raise DatabaseError(
                        DatabaseErrorCode.QUERY_REJECTED,
                        "The database rejected a non-query operation.",
                    )
                columns = tuple(str(description[0]) for description in cursor.description)
                fetched = cursor.fetchmany(self._max_rows + 1)
        except DatabaseError:
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            message = str(exc).casefold()
            code = (
                DatabaseErrorCode.QUERY_REJECTED
                if "authorized" in message or "one statement" in message
                else DatabaseErrorCode.EXECUTION_FAILED
            )
            raise DatabaseError(
                code,
                "The validated query could not be executed safely.",
            ) from exc

        truncated = len(fetched) > self._max_rows
        rows = tuple(
            tuple(serialize_sqlite_value(value) for value in row)
            for row in fetched[: self._max_rows]
        )
        return QueryResult(columns=columns, rows=rows, truncated=truncated)

    def _connect(self) -> sqlite3.Connection:
        if not self._path.is_file():
            raise DatabaseError(
                DatabaseErrorCode.UNAVAILABLE,
                "The demo database is unavailable. Run the initialization command.",
            )
        resolved = self._path.resolve()
        uri_path = quote(resolved.as_posix(), safe="/:")
        connection = sqlite3.connect(
            f"file:{uri_path}?mode=ro",
            uri=True,
            timeout=5,
        )
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        return connection

    @staticmethod
    def _columns_for_table(
        connection: sqlite3.Connection,
        table_name: str,
    ) -> tuple[ColumnSchema, ...]:
        rows = connection.execute(
            "SELECT name, type, [notnull], pk FROM pragma_table_info(?) ORDER BY cid",
            (table_name,),
        ).fetchall()
        return tuple(
            ColumnSchema(
                name=str(name),
                declared_type=str(declared_type),
                nullable=not bool(not_null),
                primary_key=bool(primary_key),
            )
            for name, declared_type, not_null, primary_key in rows
        )


def serialize_sqlite_value(value: Any) -> Any:
    """Convert driver values into bounded UI- and JSON-safe values."""

    if value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, bytes):
        return f"<binary:{len(value)} bytes>"
    text = str(value)
    return f"{text[:500]}…" if len(text) > 500 else text


def _read_only_authorizer(
    action: int,
    _arg1: str | None,
    _arg2: str | None,
    _database: str | None,
    _trigger: str | None,
) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_AUTHORIZER_ACTIONS else sqlite3.SQLITE_DENY
