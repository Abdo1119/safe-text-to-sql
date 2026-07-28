from __future__ import annotations

from pathlib import Path

import pytest

from safe_text_to_sql.database.initializer import initialize_database
from safe_text_to_sql.database.sqlite import (
    DatabaseError,
    DatabaseErrorCode,
    SQLiteRepository,
)
from safe_text_to_sql.models import ValidatedSQLQuery
from safe_text_to_sql.sql.guard import SQLGuard
from safe_text_to_sql.sql.policies import SQLPolicy


def _repository(tmp_path: Path, *, max_rows: int = 200) -> SQLiteRepository:
    path = tmp_path / "demo.sqlite"
    initialize_database(path)
    return SQLiteRepository(path, max_rows=max_rows)


def _validated(sql: str, *, limit: int = 200) -> ValidatedSQLQuery:
    return ValidatedSQLQuery(
        sql=sql,
        referenced_tables=(),
        effective_limit=limit,
        limit_was_added=False,
        limit_was_clamped=False,
    )


def test_initialization_and_schema_introspection(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    schema = repository.introspect_schema()

    assert schema.table_names == (
        "Album",
        "Artist",
        "Customer",
        "Employee",
        "Genre",
        "Invoice",
        "InvoiceLine",
        "Track",
    )
    assert '"CustomerId" INTEGER PRIMARY KEY' in schema.render_for_prompt()
    assert repository.healthcheck()


@pytest.mark.parametrize(
    ("sql", "expected_columns"),
    [
        ('SELECT "FirstName" FROM "Customer" ORDER BY "CustomerId" LIMIT 2', ("FirstName",)),
        (
            'SELECT c."FirstName", i."Total" FROM "Customer" AS c '
            'JOIN "Invoice" AS i ON c."CustomerId" = i."CustomerId" '
            'ORDER BY i."InvoiceId" LIMIT 2',
            ("FirstName", "Total"),
        ),
        (
            'SELECT "BillingCountry", SUM("Total") AS Revenue FROM "Invoice" '
            'GROUP BY "BillingCountry" ORDER BY Revenue DESC LIMIT 3',
            ("BillingCountry", "Revenue"),
        ),
        (
            'WITH totals AS (SELECT "CustomerId", SUM("Total") AS Spent FROM "Invoice" '
            'GROUP BY "CustomerId") SELECT * FROM totals ORDER BY Spent DESC LIMIT 3',
            ("CustomerId", "Spent"),
        ),
        (
            'SELECT "CustomerId", RANK() OVER (ORDER BY "Total" DESC) AS SalesRank '
            'FROM "Invoice" ORDER BY SalesRank LIMIT 3',
            ("CustomerId", "SalesRank"),
        ),
    ],
)
def test_executes_read_only_analytics(
    tmp_path: Path,
    sql: str,
    expected_columns: tuple[str, ...],
) -> None:
    repository = _repository(tmp_path)

    result = repository.execute(_validated(sql))

    assert result.columns == expected_columns
    assert result.rows
    assert len(result.rows) <= 3


def test_caps_rows_even_if_validated_query_claims_a_larger_limit(tmp_path: Path) -> None:
    repository = _repository(tmp_path, max_rows=2)

    result = repository.execute(
        _validated('SELECT "CustomerId" FROM "Customer" ORDER BY "CustomerId"', limit=999)
    )

    assert len(result.rows) == 2
    assert result.truncated


@pytest.mark.parametrize(
    "sql",
    [
        'DELETE FROM "Customer"',
        'UPDATE "Customer" SET "FirstName" = \'Changed\'',
        'CREATE TABLE "Unsafe" ("id" INTEGER)',
        "SELECT 1; SELECT 2",
    ],
)
def test_database_level_controls_reject_writes_and_multiple_statements(
    tmp_path: Path,
    sql: str,
) -> None:
    repository = _repository(tmp_path)

    with pytest.raises(DatabaseError) as exc_info:
        repository.execute(_validated(sql))

    assert exc_info.value.code is DatabaseErrorCode.QUERY_REJECTED


def test_guard_and_repository_reject_unknown_table(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    schema = repository.introspect_schema()
    guard = SQLGuard(
        SQLPolicy(
            allowed_schemas=frozenset(),
            allowed_tables=frozenset(name.casefold() for name in schema.table_names),
            max_rows=200,
        )
    )

    validation = guard.validate('SELECT * FROM "PrivateTable"')

    assert not validation.is_valid


def test_missing_database_error_does_not_expose_local_path(tmp_path: Path) -> None:
    missing = tmp_path / "private" / "missing.sqlite"
    repository = SQLiteRepository(missing, max_rows=10)

    with pytest.raises(DatabaseError) as exc_info:
        repository.healthcheck()

    assert exc_info.value.code is DatabaseErrorCode.UNAVAILABLE
    assert str(missing) not in str(exc_info.value)
